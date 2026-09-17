import os
import math
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("winscore")

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_KEY = os.environ["API_FOOTBALL_KEY"]
API_BASE = "https://v3.football.api-sports.io"

# --- API-Football helpers -----------------------------------------------

def af_get(endpoint, params):
    headers = {"x-apisports-key": API_KEY}
    r = requests.get(f"{API_BASE}/{endpoint}", headers=headers, params=params, timeout=15)
    if not r.ok:
        # log the response body so the real reason (bad key, plan limit, etc.) shows up in Render logs
        log.error("API-Football %s response: %s", r.status_code, r.text[:500])
    r.raise_for_status()
    data = r.json()
    # log_ result count + any API-side error/warning even on a 200 OK, so empty
    # results (wrong team id, plan restriction, etc.) are visible in Render logs
    log.info(
        "API-Football %s params=%s -> results=%s errors=%s",
        endpoint, params, data.get("results"), data.get("errors"),
    )
    return data


def search_team(name):
    data = af_get("teams", {"search": name})
    resp = data.get("response", [])
    if not resp:
        return None
    team = resp[0]["team"]
    log.info("search_team(%r) matched id=%s name=%s", name, team["id"], team["name"])
    return team


def last_fixtures(team_id, n=10):
    data = af_get("fixtures", {"team": team_id, "last": n})
    return data.get("response", [])


def next_fixture(team_id):
    data = af_get("fixtures", {"team": team_id, "next": 1})
    resp = data.get("response", [])
    return resp[0] if resp else None


# --- Stats computation ----------------------------------------------------

def compute_stats(fixtures, team_id):
    s = {
        "played": 0, "wins": 0, "draws": 0, "losses": 0,
        "gf": 0, "ga": 0,
        "home_played": 0, "home_gf": 0, "home_ga": 0,
        "away_played": 0, "away_gf": 0, "away_ga": 0,
    }
    for fx in fixtures:
        teams = fx["teams"]
        goals = fx["goals"]
        if goals["home"] is None or goals["away"] is None:
            continue
        is_home = teams["home"]["id"] == team_id
        gf = goals["home"] if is_home else goals["away"]
        ga = goals["away"] if is_home else goals["home"]
        s["played"] += 1
        s["gf"] += gf
        s["ga"] += ga
        if is_home:
            s["home_played"] += 1
            s["home_gf"] += gf
            s["home_ga"] += ga
        else:
            s["away_played"] += 1
            s["away_gf"] += gf
            s["away_ga"] += ga
        if gf > ga:
            s["wins"] += 1
        elif gf == ga:
            s["draws"] += 1
        else:
            s["losses"] += 1
    return s


def avg(a, b):
    return a / b if b else 0.0


# --- Poisson prediction -----------------------------------------------------

def poisson_pmf(k, lam):
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def predict(lam_home, lam_away, max_goals=6):
    p_home = p_draw = p_away = 0.0
    for i in range(max_goals):
        for j in range(max_goals):
            p = poisson_pmf(i, lam_home) * poisson_pmf(j, lam_away)
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p
    return p_home, p_draw, p_away


# --- Telegram handlers -------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "გამარჯობა! მე ვარ Win Score.\n\n"
        "დამიწერე ფეხბურთის გუნდის სახელი (ინგლისურად, მაგ: Real Madrid) "
        "და გამოგიგზავნი სტატისტიკას ბოლო 10 მატჩზე და პროგნოზს მომდევნო თამაშზე."
    )


async def handle_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    await update.message.reply_text("ვეძებ...")

    try:
        team = search_team(query)
        if not team:
            await update.message.reply_text("გუნდი ვერ მოიძებნა, სცადე სხვა დაწერილობა (ინგლისურად).")
            return

        team_id = team["id"]
        fixtures = last_fixtures(team_id, 10)
        s = compute_stats(fixtures, team_id)

        msg = [f"📊 {team['name']} — ბოლო {s['played']} მატჩი\n"]
        msg.append(f"მოგება: {s['wins']} | ფრე: {s['draws']} | წაგება: {s['losses']}")
        msg.append(f"საშუალოდ გაიტანა: {avg(s['gf'], s['played']):.2f} | გაუშვა: {avg(s['ga'], s['played']):.2f}")
        msg.append(
            f"სახლში — გაიტანა: {avg(s['home_gf'], s['home_played']):.2f}, "
            f"გაუშვა: {avg(s['home_ga'], s['home_played']):.2f} ({s['home_played']} მატჩი)"
        )
        msg.append(
            f"გასვლაზე — გაიტანა: {avg(s['away_gf'], s['away_played']):.2f}, "
            f"გაუშვა: {avg(s['away_ga'], s['away_played']):.2f} ({s['away_played']} მატჩი)"
        )

        nxt = next_fixture(team_id)
        if nxt:
            home = nxt["teams"]["home"]
            away = nxt["teams"]["away"]
            date = nxt["fixture"]["date"][:16].replace("T", " ")
            is_team_home = home["id"] == team_id
            opponent = away if is_team_home else home
            opp_fixtures = last_fixtures(opponent["id"], 10)
            opp_s = compute_stats(opp_fixtures, opponent["id"])

            if is_team_home:
                lam_home = (avg(s["home_gf"], s["home_played"]) + avg(opp_s["away_ga"], opp_s["away_played"])) / 2 or avg(s["gf"], s["played"])
                lam_away = (avg(opp_s["away_gf"], opp_s["away_played"]) + avg(s["home_ga"], s["home_played"])) / 2 or avg(opp_s["gf"], opp_s["played"])
            else:
                lam_away = (avg(s["away_gf"], s["away_played"]) + avg(opp_s["home_ga"], opp_s["home_played"])) / 2 or avg(s["gf"], s["played"])
                lam_home = (avg(opp_s["home_gf"], opp_s["home_played"]) + avg(s["away_ga"], s["away_played"])) / 2 or avg(opp_s["gf"], opp_s["played"])

            p_home, p_draw, p_away = predict(max(lam_home, 0.05), max(lam_away, 0.05))

            msg.append(f"\n⚽️ მომდევნო მატჩი: {home['name']} — {away['name']}")
            msg.append(f"თარიღი: {date}")
            msg.append(f"მოსალოდნელი გოლები: {home['name']} {lam_home:.1f} — {lam_away:.1f} {away['name']}")
            msg.append(
                f"შანსები — {home['name']} მოგება: {p_home*100:.0f}%, "
                f"ფრე: {p_draw*100:.0f}%, {away['name']} მოგება: {p_away*100:.0f}%"
            )
        else:
            msg.append("\nმომდევნო მატჩის ინფორმაცია ვერ მოიძებნა.")

        await update.message.reply_text("\n".join(msg))

    except requests.HTTPError as e:
        log.exception("API error")
        await update.message.reply_text("API-ს შეცდომა, სცადე მოგვიანებით (შეიძლება დღიური ლიმიტი ამოწურულია).")
    except Exception:
        log.exception("Unexpected error")
        await update.message.reply_text("რაღაც შეცდომა მოხდა, სცადე თავიდან.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_team))

    port = int(os.environ.get("PORT", 8443))
    external_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

    if external_host:
        # Webhook mode — used on Render
        webhook_url = f"https://{external_host}/{BOT_TOKEN}"
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url,
        )
    else:
        # Polling mode — used for local testing
        app.run_polling()


if __name__ == "__main__":
    main()

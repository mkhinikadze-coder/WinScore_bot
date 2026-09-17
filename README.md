# Win Score — ტელეგრამ ბოტი

ფეხბურთის გუნდის სახელზე პასუხობს ბოლო 10 მატჩის სტატისტიკით (მოგება/ფრე/წაგება, საშუალო გატანილი/გაშვებული გოლები სახლში და გასვლაზე) და პროგნოზით მომდევნო მატჩზე.

## რა დაგჭირდება (ორივე უფასოა)

1. **Telegram Bot Token** — @BotFather-თან `/newbot`, დაარქვი სახელი, მიიღებ token-ს.
2. **API-Football key** — დარეგისტრირდი https://dashboard.api-football.com უფასოდ (Free გეგმა: 100 request/დღეში). Dashboard-ზე ნახავ API key-ს.

⚠️ 100 request/დღეში ნიშნავს დაახლ. 20-25 მოთხოვნას დღეში (თითო გუნდის შემოწმება ~4 request-ს ხარჯავს), ასე რომ პირადი/მცირე გამოყენებისთვის საკმარისია.

## Deploy — GitHub + Render

1. შექმენი ახალი, ცალკე repo GitHub-ზე (მაგ. `win-score-bot`) — არსებულ ბოტს ნუ შეურევ.
2. ატვირთე ეს ოთხი ფაილი (`bot.py`, `requirements.txt`, `render.yaml`, `README.md`) repo-ში.
3. Render.com-ზე: **New → Web Service** → დააკავშირე ეს repo.
4. Environment-ში დაამატე ორი ცვლადი:
   - `BOT_TOKEN` — BotFather-ის token
   - `API_FOOTBALL_KEY` — api-football-ის key
5. Plan აირჩიე **Free**. Build command და Start command `render.yaml`-იდან ავტომატურად წაიკითხება.
6. Deploy-ის შემდეგ Render თავად ანიჭებს `RENDER_EXTERNAL_HOSTNAME`-ს — ბოტი ამის მიხედვით თავად აყენებს webhook-ს (კოდში უკვე გათვალისწინებულია).

## შენიშვნა Free გეგმაზე

Render-ის free web service 15 წუთის უმოქმედობის შემდეგ "იძინებს" — პირველი შეტყობინება ამ დროის შემდეგ ~30-60 წამით დაგვიანებით მოვა, შემდეგი უკვე სწრაფად.

## ლოკალურად ტესტირება

```
pip install -r requirements.txt
export BOT_TOKEN=...
export API_FOOTBALL_KEY=...
python bot.py
```
(RENDER_EXTERNAL_HOSTNAME რომ არაა დაყენებული, ბოტი polling რეჟიმში გაეშვება).

# YouSplit

🇩🇪 **Deutsche Version: [README.md](README.md)**

Track shared expenses and see at a glance who owes whom how much.

## What is it about?

The idea behind YouSplit is simple: you want to **see without much effort
who spends how much on groceries each month** and **how high the shared
expenses are**.

You don't need a user account or a cloud service. Create a list, share the
link with your flatmates or family, and everyone adds their expenses there.
YouSplit works out who still owes money to whom.

## The easiest way: upload your bank statement once a month

Typing in every expense by hand is tedious. This is faster:

1. **Each person uploads their bank statement once a month** (as a PDF from
   online banking).
2. **YouSplit detects grocery purchases automatically** and ticks them for you.
3. **Take a quick look:** Is everything right? If a purchase is missing, tick
   it. If one doesn't belong, untick it.
4. Select who paid and click **"Buchungen anlegen"** (create bookings). Done.
5. **Delete the bank statement afterwards.** YouSplit doesn't keep the PDF
   anyway. Only the ticked purchases are saved, with date, amount and shop.

**Why this is safe:** YouSplit runs on your own device or server. Your bank
statement is processed there and is never sent anywhere else. Your sensitive
banking data does not end up with any third party.

Good to know:

- It works with PDFs where you can select the text, the way online banking
  provides them. Scanned paper statements don't work.
- The parser is built for German bank statement formats.
- Expenses that are already in the list are recognized and not ticked twice.
- Drugstores such as dm or Rossmann count as groceries, because people often
  buy food there too.

### Which shops are recognized

The shops are listed in
[`backend/food_merchants.txt`](backend/food_merchants.txt). I put this list
together by hand. It focuses on **well-known supermarkets, discounters,
bakeries and butchers from Germany and Europe**, plus large chains from other
countries.

The list is certainly not complete. If your shop is missing, you can simply
add it yourself. The format is explained at the top of the file.

## Features

- Lists without user accounts, shared by link
- Expenses with payer, category and date
- Bank statement import for grocery purchases
- Flexible cost splitting: equally, by percentage, by amount or by shares
- Settle-up: who has to pay whom how much
- Statistics by category and person
- Foreign currencies, automatically converted to euros

## Your data

**Everything you enter stays on the device that runs YouSplit.** There is no
cloud, no advertising and no analytics.

Only for expenses in a foreign currency does YouSplit fetch the current
exchange rate from [Frankfurter](https://www.frankfurter.app). Only the
currency code is sent (for example "USD"), no amounts and no names.

**Important:** Anyone who has the link to a list can view and edit it. Only
share the link with people who are supposed to take part.

## Installation

### In Home Assistant (add-on)

1. In Home Assistant: *Settings → Add-ons → Add-on Store → ⋮ → Repositories*
2. Add this address: `https://github.com/car-mechanic/YouSplit`
3. Install and start **YouSplit**
4. Open `http://<home-assistant-ip>:8099` in your browser

Your data is automatically included in Home Assistant backups.
More details: [`yousplit/DOCS.md`](yousplit/DOCS.md) (German)

### As a single Docker container (without Home Assistant)

One container includes everything: database and user interface.

```bash
docker run -d --init --name yousplit -p 8099:8099 \
  -v yousplit-data:/data --restart unless-stopped \
  ghcr.io/car-mechanic/yousplit-addon-amd64
```

- On a Raspberry Pi 4 or 5, use `aarch64` instead of `amd64`.
- Then open `http://<device-ip>:8099` in your browser.
- Your data is stored in the Docker volume `yousplit-data`.
- Please keep `--init`. Without it, the database is not shut down cleanly
  when the container stops.

Prefer to build it yourself?

```bash
docker build -f Dockerfile.addon -t yousplit .
```

### For development (Docker Compose)

Frontend, backend and database run in separate containers. Code changes show
up immediately.

```bash
docker compose up --build
```

- User interface: http://localhost:5173
- API documentation: http://localhost:8000/docs

## Tech stack

React + TypeScript (Vite, Tailwind) · FastAPI · PostgreSQL

## License

[GNU AGPL-3.0](LICENSE). You may use, modify and share YouSplit freely. If you
offer a modified version as an online service, you must publish your modified
source code as well.

Note: the user interface is currently available in German only.

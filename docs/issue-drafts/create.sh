#!/bin/sh
# Einmalig: legt Labels und die 8 Issues an (Voraussetzung: gh auth login).
# Issue 8 verweist auf die echte Nummer von Issue 7. Danach docs/issue-drafts
# und den Hinweis in CLAUDE.md loeschen.
set -e
GH=gh
R=car-mechanic/YouSplit
D="$(dirname "$0")"
"$GH" label create tech-debt -R $R -c d4c5f9 -d "Known shortcuts to pay back" --force >/dev/null
"$GH" label create security -R $R -c b60205 -d "Security and exposure" --force >/dev/null
"$GH" label create bank-statement -R $R -c 0e8a16 -d "Bank statement import" --force >/dev/null
mk() { "$GH" issue create -R $R -t "$1" -l "$2" -F "$3" ; }
mk "Introduce Alembic for database migrations" tech-debt "$D/1.md"
mk "Make CORS origins configurable" tech-debt "$D/2.md"
mk "Close test gaps: settlement, splits, currency, CRUD" tech-debt "$D/3.md"
mk "Decide on access protection for shared lists" security "$D/4.md"
mk "Production-ready Docker Compose setup" security "$D/5.md"
mk "Test bank statement parser with real statements" bank-statement "$D/6.md"
U7=$(mk "Add endpoints and UI for category rules" bank-statement "$D/7.md")
echo "$U7"
N7=${U7##*/}
sed "s/#7/#$N7/" "$D/8.md" > "$D/8.final.md"
mk "Analyze full bank statements" bank-statement "$D/8.final.md"

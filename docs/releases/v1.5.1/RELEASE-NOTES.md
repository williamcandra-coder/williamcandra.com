# Release Notes — v1.5.1

Small change. One file.

## Back-link label changes after the reading

Before consulting, the link out of the page reads **"NOT TODAY, UNCLE"** — a way
to decline. Once uncle has actually said his piece, declining makes no sense.
The label now becomes a way to take your leave instead.

Eleven send-offs, picked from the chart so a person doesn't get the same one
every consult:

```
THANK YOU, UNCLE      NOTED, UNCLE
ENOUGH, UNCLE         RUDE. ACCURATE.
OKAY OKAY, UNCLE      YOU'RE THE WORST
I HEARD YOU, UNCLE    SEE YOU NEXT YEAR
BYE, UNCLE            FINE. FINE. FINE.
                      UNCLE, PLEASE STOP
```

- Reverts to "NOT TODAY, UNCLE" when the visitor restarts.
- Applies on shared-link replays too, since it's set in `renderReading`.

### One constraint worth noting

Labels are capped at **19 characters**. The link is 7px Press Start 2P with 1px
letter-spacing, so a long label pushes past the cabinet edge on a narrow phone —
"SEE YOU IN A YEAR, UNCLE" was 24 characters, 50% wider than the baseline, and
would have overflowed. Trimmed rather than shipped. If you add your own, keep
them at 19 or under.

## Unchanged

Everything from v1.5.0: solar terms to the minute, true element count, ten
sections, four notable years, rebuilt Love & Spouse, no engine jargon.

## Editing

`BACK_BEFORE` and `BACK_AFTER` near the top of the UI wiring section in
`goh-pok-tong.html`.

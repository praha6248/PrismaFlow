# Validating PrismaFlow itself

PrismaFlow asks its users to test demand before building. This plan applies the same rule to
PrismaFlow. The goal is to learn, from past behaviour rather than opinions, whether people who look
for product ideas have a problem painful enough to change tools for.

## Hypotheses

| # | Hypothesis | Confirmed when | Rejected when |
| --- | --- | --- | --- |
| H1 | Indie makers and junior product designers spend 5+ hours on research before committing to an idea. | 3 of 5 describe a recent idea where research took a weekend or longer. | Most picked their last idea in under an hour or by gut feeling. |
| H2 | The research is scattered across tools (Google, Reddit, spreadsheets, notes, ChatGPT). | 3 of 5 name three or more tools for their last idea. | Most use one tool they are happy with. |
| H3 | They abandoned at least one built product because nobody wanted it. | 3 of 5 tell a concrete story with a time or money cost. | Nobody has shipped and failed yet. |
| H4 | Privacy or cost keeps some of them away from cloud AI tools. | 2 of 5 avoided or stopped paying for a tool for that reason. | Nobody mentions it when asked about their last tool change. |
| H5 | They already pay for something in this space. | 2 of 5 paid for a course, template, research tool or consultant in the last year. | Nobody has spent money on idea validation. |

## Who to talk to

- Indie makers who shipped at least one side project in the last two years.
- Junior and mid product or UX designers who run discovery for a client or employer.
- Students in design, product or entrepreneurship programmes working on a thesis product.

Leave out friends and family. They are polite, and polite answers are noise.

## Where to find them

| Channel | Approach | Target |
| --- | --- | --- |
| Indie Hackers, Lemmy and Bluesky maker communities | A post asking about the last idea people dropped, not about PrismaFlow | 3 interviews |
| University design and entrepreneurship groups | Ask a lecturer to share a 20-minute research call | 3 interviews |
| Polish product and UX Slack/Discord communities | Direct message to people who posted about discovery or research | 2 interviews |
| GitHub stargazers and issue authors | Thank them and ask for a call | 2 interviews |

Aim for 10 interviews, five per segment, over two weeks. Book 20-minute calls and record notes
right after each one.

## Screener

1. When did you last start working on a new product idea?
2. What did you do before deciding to build it?
3. Did you build it? What happened next?

Invite people who answered the first question with "in the last six months" and the second with
something concrete.

## Interview script (Mom Test)

Ask about the past and specifics. Do not pitch PrismaFlow until the last minute, and do not ask
whether they would use it.

1. Tell me about the last product idea you seriously considered.
2. How did you decide whether it was worth building?
3. Walk me through what you did, step by step. Which tools did you open?
4. How long did that take, roughly?
5. What was the most annoying part?
6. What did you do when the research gave mixed signals?
7. Have you ever built something that nobody used? What did it cost you?
8. Have you paid for anything to help with this: a course, a tool, a template, a person?
9. Is there anything you tried and stopped using? Why?
10. Who else do you know who goes through this?

Close by asking for an introduction to the person from question 10. A yes is a stronger signal
than praise.

## Signals

Strong: a concrete recent story, money already spent, a workaround they built themselves,
an introduction to someone else, a request to try a build.

Weak: "that sounds useful", "I would definitely use that", hypothetical future plans,
compliments.

Log each interview in the Validate step of a PrismaFlow project created for this niche, so that
verdicts are only counted when backed by a quote from the notes.

## Decision after 10 interviews

- **Continue** if H1 and H3 are confirmed and at least one of H4 or H5 is confirmed.
- **Narrow** to the segment that confirmed most hypotheses if the segments disagree.
- **Rethink** if H1 or H3 is rejected. The pain is not there, and features will not create it.

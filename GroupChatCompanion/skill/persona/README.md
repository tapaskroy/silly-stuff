# Persona files

The skill loads four files before every run. Three hold personal data and are gitignored.
One ships as it is.

| file | what it holds |
|---|---|
| `SOUL.md` | Conduct. Generic, no personal data. Ships as it is. |
| `IDENTITY.template.md` | Copy to `IDENTITY.md`. Who your agent is: name, emoji, vibe. |
| `USER.template.md` | Copy to `USER.md`. Who it works for, and the hard privacy walls. |
| `MEMORY.template.md` | Copy to `MEMORY.md`. The durable logbook. Start with the Conduct section. |

Before the first run:

```sh
cd skill/persona
cp IDENTITY.template.md IDENTITY.md
cp USER.template.md     USER.md
cp MEMORY.template.md   MEMORY.md
```

Those three copies are already listed in `.gitignore`. Confirm that before you put anything
real in them, because a filled-in `USER.md` holds exactly the data this project tells you
not to publish.

`SOUL.md` is deliberately not a template. It is conduct rather than configuration and it
describes no particular person, so there is nothing to fill in. Edit it if you disagree with
it, and say so in the commit message: an agent whose conduct changed silently is harder to
reason about afterwards.

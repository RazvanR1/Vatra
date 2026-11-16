# Translating Vatra

Thank you for helping! Each language is **one file**, plus a small file for the app's settings form.
You don't need to know Python or JavaScript, and you don't need to translate everything at once:
anything left untranslated simply shows in English.

## Files for a language (example: Hungarian, `hu`)

| File | What it contains |
|---|---|
| `ha_home_brain/app/locales/hu.json` | Everything Vatra says: notifications, alerts, weekly report, AI prompts (`app` section) and the web panel (`panel` section). |
| `ha_home_brain/translations/hu.yaml` | Names and descriptions of the options in *Settings → Apps → Vatra → Configuration* (Home Assistant's own format). |

## Steps

1. Copy `ha_home_brain/app/locales/en.json` to `ha_home_brain/app/locales/<code>.json`
   (`<code>` = the language code Home Assistant uses: `hu`, `de`, `fr`, `pt-BR`…).
2. Change `_meta`: `"name"` is the language name in that language (`"Magyar"`), `"locale"` is used
   for dates (`"hu-HU"`).
3. Translate the **values** (right side). Keep the **keys** (left side) exactly as they are.
   You may delete lines you don't want to translate yet – they fall back to English.
4. Copy `ha_home_brain/translations/en.yaml` to `<code>.yaml` and translate the `name:` and
   `description:` texts.
5. Open a pull request. The tests check the file automatically; the language then appears in the panel's
   language list and in the `language` option.

## Rules that keep things working

- **Placeholders** in braces stay exactly as they are, untranslated: `{name}`, `{n}`, `{state}`…
  You can move them inside the sentence. Example: `"{name} is home"` → `"{name} otthon van"`.
- In the `app` section, **double braces** `{{` `}}` are literal braces in AI prompts (for example a JSON
  example). Keep them doubled.
- `\n` is a line break – keep it.
- The AI prompts (keys starting with `agent.` and `jarvis.`) tell the model what to do and in which
  language to answer. Translate them naturally, and keep the instruction to answer in your language.
- Keep it short: notifications appear on phone lock screens.

## Check your file locally (optional)

```bash
pip install pytest tzdata
python -m pytest tests/test_i18n.py -q
```

The panel shows how much of each language is translated (for example `Magyar (64%)`).
Questions? Open an issue with the **🌍 New language** template.

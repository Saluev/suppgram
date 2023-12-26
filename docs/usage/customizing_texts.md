# Customizing texts

Suppgram encapsulates all text generation in [TextProvider][suppgram.texts.TextProvider] class.

::: suppgram.texts.TextProvider
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 2

It has a lot of members, see [source code](https://github.com/Saluev/suppgram/blob/master/suppgram/texts/interface.py)
for details.

Suppgram also provides out-of-the-box text pack for English and Russian languages.

::: suppgram.texts.en.EnglishTextProvider
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 2

::: suppgram.texts.ru.RussianTextProvider
    handler: python
    options:
      show_root_heading: true
      show_source: false
      heading_level: 2

If you want to customize your texts, you can either implement your own `TextProvider` or tweak an
existing one. For example, let's say we want to hide customer contacts from agents for some privacy reasons.
Our code would look like the following:

```python
# ./mytexts.py

from suppgram.texts.en import EnglishTextProvider


class MyTextProvider(EnglishTextProvider):
    customer_profile_contacts = "📒 Contacts: (hidden)"
```

Then we can customize texts provider in all-in-one CLI:
```shell
$ python -m suppgram.cli.all_in_one \
         --sqlalchemy-uri sqlite+aiosqlite:///test.db \
         --telegram-owner-id <your Telegram user ID> \
         --texts mytexts.MyTextProvider
```
or via builder:
```python
from suppgram.builder import Builder

from mytexts import MyTextProvider


builder = Builder()
...
builder = builder.with_texts(MyTextProvider())
```

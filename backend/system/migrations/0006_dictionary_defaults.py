from django.db import migrations


def seed(apps, schema_editor):
    Word = apps.get_model("system", "DictionaryWord")
    for replacement, variants in (("LTDA", []), ("S/A", ["sa.", "s.a.", "s.a"])):
        Word.objects.get_or_create(replacement=replacement, defaults={"variants": variants})


class Migration(migrations.Migration):
    dependencies = [("system", "0005_word_dictionary")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

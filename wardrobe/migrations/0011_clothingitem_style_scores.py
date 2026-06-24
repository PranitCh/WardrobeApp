from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wardrobe", "0010_clothingitem_color_names_alter_userpreference_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="clothingitem",
            name="style_scores",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]


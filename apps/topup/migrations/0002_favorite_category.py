from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("topup", "0001_initial")]

    operations = [
        migrations.AddField(model_name="favoritenumber", name="category", field=models.CharField(blank=True, max_length=60)),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("shopkeepers", "0002_service_controls")]

    operations = [
        migrations.AddField(model_name="shopkeeperprofile", name="contact_number", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="shopkeeperprofile", name="directions", field=models.TextField(blank=True)),
        migrations.AddField(model_name="shopkeeperprofile", name="service_tags", field=models.TextField(blank=True)),
        migrations.AddField(model_name="shopkeeperprofile", name="shop_description", field=models.TextField(blank=True)),
        migrations.AddField(model_name="shopkeeperprofile", name="top_selling_items", field=models.TextField(blank=True)),
    ]

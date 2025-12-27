from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lms", "0003_courseproduct_enrollmentrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollmentrecord",
            name="stripe_checkout_session_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="enrollmentrecord",
            name="stripe_payment_intent_id",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]

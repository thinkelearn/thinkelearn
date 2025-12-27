from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("lms", "0004_enrollmentrecord_stripe_ids"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="usd", max_length=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("initiated", "Initiated"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        default="initiated",
                        max_length=20,
                    ),
                ),
                ("stripe_checkout_session_id", models.CharField(blank=True, max_length=255)),
                ("stripe_payment_intent_id", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "enrollment_record",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="payments",
                        to="lms.enrollmentrecord",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]

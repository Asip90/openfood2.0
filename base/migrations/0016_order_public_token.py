import uuid

from django.db import migrations, models


def populate_public_tokens(apps, schema_editor):
    Order = apps.get_model('base', 'Order')
    for order in Order.objects.filter(public_token__isnull=True).only('id'):
        order.public_token = uuid.uuid4()
        order.save(update_fields=['public_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0015_pushsubscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='public_token',
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_public_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='public_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

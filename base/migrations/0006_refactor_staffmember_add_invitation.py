import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_staffmember_and_preparing_by'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Remove old unique_together constraint
        migrations.AlterUniqueTogether(
            name='staffmember',
            unique_together=set(),
        ),
        # 2. Remove old fields
        migrations.RemoveField(model_name='staffmember', name='first_name'),
        migrations.RemoveField(model_name='staffmember', name='last_name'),
        migrations.RemoveField(model_name='staffmember', name='username'),
        migrations.RemoveField(model_name='staffmember', name='password'),
        # 3. Add user OneToOneField (nullable temporarily to allow migration on existing rows)
        migrations.AddField(
            model_name='staffmember',
            name='user',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='staff_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # 4. Delete all existing StaffMember rows (dev environment, no real data)
        migrations.RunSQL(
            sql='DELETE FROM base_staffmember;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 5. Make user non-nullable now that rows are cleared
        migrations.AlterField(
            model_name='staffmember',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='staff_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # 6. Add new unique_together
        migrations.AlterUniqueTogether(
            name='staffmember',
            unique_together={('user', 'restaurant')},
        ),
        # 7. Create StaffInvitation model
        migrations.CreateModel(
            name='StaffInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField()),
                ('role', models.CharField(
                    choices=[('coadmin', 'Co-administrateur'), ('cuisinier', 'Cuisinier'), ('serveur', 'Serveur')],
                    max_length=20,
                )),
                ('token', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('accepted', models.BooleanField(default=False)),
                ('expires_at', models.DateTimeField()),
                ('restaurant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invitations',
                    to='base.restaurant',
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_invitations',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]

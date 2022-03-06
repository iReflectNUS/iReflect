# Generated by Django 4.0.2 on 2022-02-20 17:14

from django.db import migrations, models
import django.db.models.deletion
import django_update_from_dict


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('content_delivery_service', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserInvite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('email', models.EmailField(max_length=254, unique=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(django_update_from_dict.UpdateFromDictMixin, models.Model),
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('profile_image', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='content_delivery_service.image')),
            ],
            options={
                'abstract': False,
            },
            bases=(django_update_from_dict.UpdateFromDictMixin, models.Model),
        ),
    ]
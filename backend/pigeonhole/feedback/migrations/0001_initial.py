# Generated by Django 4.0.5 on 2024-09-12 19:12

from django.db import migrations, models
import django.db.models.deletion
import pigeonhole.common.utils


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0004_coursesubmissionviewablemember_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeedbackInitialResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('question', models.CharField(max_length=1000)),
                ('initial_response', models.TextField()),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.course')),
                ('creator', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='courses.coursemembership')),
                ('milestone', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='courses.coursemilestone')),
                ('template', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='courses.coursemilestonetemplate')),
            ],
            options={
                'unique_together': {('course', 'milestone', 'template', 'creator', 'question')},
            },
            bases=(pigeonhole.common.utils.UpdateFromDictMixin, models.Model),
        ),
    ]
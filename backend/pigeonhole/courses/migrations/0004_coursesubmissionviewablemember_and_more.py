# Generated by Django 4.0.5 on 2022-08-16 13:41

from django.db import migrations, models
import django.db.models.deletion
import pigeonhole.common.utils


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_coursesubmissioncomment_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseSubmissionViewableMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.coursemembership')),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.coursesubmission')),
            ],
            bases=(pigeonhole.common.utils.UpdateFromDictMixin, models.Model),
        ),
        migrations.CreateModel(
            name='CourseSubmissionViewableGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.coursegroup')),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.coursesubmission')),
            ],
            bases=(pigeonhole.common.utils.UpdateFromDictMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name='coursesubmissionviewablemember',
            constraint=models.UniqueConstraint(fields=('submission_id', 'member_id'), name='unique_submission_viewable_member'),
        ),
        migrations.AddConstraint(
            model_name='coursesubmissionviewablegroup',
            constraint=models.UniqueConstraint(fields=('submission_id', 'group_id'), name='unique_submission_viewable_group'),
        ),
    ]

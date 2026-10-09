from django.db import migrations


def backfill_existing_posts(apps, schema_editor):
    Announcement = apps.get_model('communications', 'Announcement')
    for post in Announcement.objects.all():
        # Keep category if already set, or normalize
        cat = post.category or 'announcement'
        if 'emergency' in cat.lower():
            cat = 'emergency'
        elif 'event' in cat.lower():
            cat = 'event'
        elif 'health' in cat.lower():
            cat = 'health'
        elif 'scholarship' in cat.lower() or 'education' in cat.lower():
            cat = 'education'
        elif 'concern' in cat.lower():
            cat = 'concern'

        post.category = cat
        post.state = 'active'
        post.audience_type = 'everyone'
        post.purok = None
        post.valid_until = None
        if not post.valid_from:
            post.valid_from = post.created_at
        post.save()


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0007_announcement_audience_type_announcement_purok_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_existing_posts, reverse_backfill),
    ]

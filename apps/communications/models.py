from django.db import models
from django.conf import settings
from django.utils import timezone
import markdown
import os
import uuid


def post_image_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"announcements/{uuid.uuid4().hex}{ext}"


class PostCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    expires = models.BooleanField(default=True, help_text="Whether posts in this category can expire")
    default_end = models.CharField(
        max_length=20,
        choices=[('end_of_month', 'End of Month'), ('none', 'None')],
        default='none'
    )
    notify_on_post = models.BooleanField(default=False, help_text="Send notification broadcast on publish")
    is_system = models.BooleanField(default=False, help_text="System categories cannot be deleted")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Post Category'
        verbose_name_plural = 'Post Categories'
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            from django.utils.text import slugify
            self.slug = slugify(self.name).replace('-', '_')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Announcement(models.Model):
    CATEGORY_ANNOUNCEMENT = 'announcement'
    CATEGORY_HEALTH = 'health'
    CATEGORY_EMERGENCY = 'emergency'
    CATEGORY_EDUCATION = 'education'
    CATEGORY_EVENT = 'event'
    CATEGORY_CONCERN = 'concern'
    CATEGORY_SCHOLARSHIP = 'scholarship'
    CATEGORY_DONATION = 'donation'
    CATEGORY_LEGISLATIVE = 'legislative'
    CATEGORY_GENERAL = 'general'
    CATEGORY_ORDINANCE = 'ordinance'

    CATEGORY_CHOICES = [
        (CATEGORY_ANNOUNCEMENT, 'Announcement'),
        (CATEGORY_HEALTH, 'Health'),
        (CATEGORY_EMERGENCY, 'Emergency Alert'),
        (CATEGORY_EDUCATION, 'Education'),
        (CATEGORY_EVENT, 'Upcoming Event'),
        (CATEGORY_CONCERN, 'Concern for Street'),
        (CATEGORY_GENERAL, 'General Advisory'),
        (CATEGORY_SCHOLARSHIP, 'Scholarship'),
        (CATEGORY_DONATION, 'Donation'),
        (CATEGORY_LEGISLATIVE, 'Legislative (Ordinance/EO)'),
        (CATEGORY_ORDINANCE, 'Barangay Ordinance'),
    ]

    AUDIENCE_EVERYONE = 'everyone'
    AUDIENCE_PUROK = 'purok'
    AUDIENCE_CHOICES = [
        (AUDIENCE_EVERYONE, 'Everyone'),
        (AUDIENCE_PUROK, 'Specific Purok'),
    ]

    STATE_ACTIVE = 'active'
    STATE_DONE = 'done'
    STATE_EXPIRED = 'expired'
    STATE_ARCHIVED = 'archived'
    STATE_CHOICES = [
        (STATE_ACTIVE, 'Active'),
        (STATE_DONE, 'Done'),
        (STATE_EXPIRED, 'Expired'),
        (STATE_ARCHIVED, 'Archived'),
    ]

    title = models.CharField(max_length=255)
    content = models.TextField(help_text='Detailed announcement content (supports Markdown formatting)')
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_ANNOUNCEMENT,
        db_index=True
    )
    audience_type = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default=AUDIENCE_EVERYONE,
        db_index=True
    )
    purok = models.ForeignKey(
        'accounts.Purok',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements'
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True, db_index=True)
    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default=STATE_ACTIVE,
        db_index=True
    )
    category_ref = models.ForeignKey(
        PostCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements'
    )
    image = models.ImageField(
        upload_to=post_image_upload_path,
        blank=True,
        null=True,
        help_text='Optional header image or poster'
    )
    is_pinned = models.BooleanField(
        default=False,
        help_text='Pin to top of resident feeds'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = 'Announcement & Feed'
        verbose_name_plural = 'Announcements & Feeds'

    def __str__(self):
        return self.title

    @property
    def rendered_html(self):
        return markdown.markdown(self.content, extensions=['extra', 'nl2br'])

    @property
    def likes_count(self):
        return self.reactions.filter(reaction_type=PostReaction.REACTION_LIKE).count()

    @property
    def supports_count(self):
        return self.reactions.filter(reaction_type=PostReaction.REACTION_SUPPORT).count()

    @property
    def importants_count(self):
        return self.reactions.filter(reaction_type=PostReaction.REACTION_IMPORTANT).count()

    @property
    def author_position(self):
        if not self.author:
            return 'Barangay Official'
        try:
            roles = list(self.author.officer_roles.all())
            if roles:
                return roles[0].get_position_display()
        except Exception:
            pass
        if self.author.role == 'admin':
            return 'Barangay Administrator'
        if self.author.role == 'kapitan':
            return 'Punong Barangay'
        return self.author.get_role_display()


Post = Announcement


class PostReaction(models.Model):
    REACTION_LIKE = 'like'
    REACTION_SUPPORT = 'support'
    REACTION_IMPORTANT = 'important'

    REACTION_CHOICES = [
        (REACTION_LIKE, 'Like'),
        (REACTION_SUPPORT, 'Support'),
        (REACTION_IMPORTANT, 'Important'),
    ]

    post = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='post_reactions'
    )
    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user', 'reaction_type')
        verbose_name = 'Post Reaction'
        verbose_name_plural = 'Post Reactions'

    def __str__(self):
        return f"{self.user.username} - {self.reaction_type} on #{self.post_id}"


class PostComment(models.Model):
    post = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='post_comments'
    )
    content = models.TextField(help_text='Comment message')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Post Comment'
        verbose_name_plural = 'Post Comments'

    def __str__(self):
        return f"{self.author.username} on #{self.post_id}: {self.content[:30]}"

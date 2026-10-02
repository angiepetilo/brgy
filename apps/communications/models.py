from django.db import models
from django.conf import settings
import markdown


class KapitanStatus(models.Model):
    STATUS_ON_DUTY = 'on_duty'
    STATUS_ON_LEAVE = 'on_leave'

    STATUS_CHOICES = [
        (STATUS_ON_DUTY, 'On Duty'),
        (STATUS_ON_LEAVE, 'On Leave'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ON_DUTY
    )
    leave_reason = models.TextField(
        blank=True,
        help_text='Reason for leave (required when setting to On Leave)'
    )
    return_date = models.DateField(
        null=True,
        blank=True,
        help_text='Expected date of return to barangay service'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kapitan_status_logs'
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Kapitan Status'
        verbose_name_plural = 'Kapitan Status Records'

    def __str__(self):
        return f"Kapitan is {self.get_status_display()} ({self.updated_at.strftime('%Y-%m-%d %H:%M')})"


class PostCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Post Category'
        verbose_name_plural = 'Post Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feed_posts')
    category = models.ForeignKey(PostCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='feed_posts')
    content = models.TextField()
    image = models.ImageField(upload_to='posts/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author.username}: {self.content[:30]}"


class Announcement(models.Model):
    CATEGORY_ANNOUNCEMENT = 'announcement'
    CATEGORY_EVENT = 'event'
    CATEGORY_EMERGENCY = 'emergency'
    CATEGORY_SCHOLARSHIP = 'scholarship'
    CATEGORY_DONATION = 'donation'
    CATEGORY_LEGISLATIVE = 'legislative'
    CATEGORY_GENERAL = 'general'
    CATEGORY_HEALTH = 'health'
    CATEGORY_ORDINANCE = 'ordinance'

    CATEGORY_CHOICES = [
        (CATEGORY_ANNOUNCEMENT, 'ANNOUNCEMENT'),
        (CATEGORY_EMERGENCY, 'EMERGENCY ALERT'),
        (CATEGORY_EVENT, 'UPCOMING EVENT'),
        (CATEGORY_SCHOLARSHIP, 'SCHOLARSHIP'),
        (CATEGORY_DONATION, 'DONATION'),
        (CATEGORY_LEGISLATIVE, 'LEGISLATIVE (ORDINANCE/EO)'),
        (CATEGORY_GENERAL, 'GENERAL ADVISORY'),
        (CATEGORY_HEALTH, 'HEALTH & SANITATION'),
        (CATEGORY_ORDINANCE, 'BARANGAY ORDINANCE'),
    ]

    title = models.CharField(max_length=255)
    content = models.TextField(help_text='Detailed announcement content (supports Markdown formatting)')
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_ANNOUNCEMENT
    )
    category_ref = models.ForeignKey(
        PostCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements'
    )
    image = models.ImageField(
        upload_to='announcements/',
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


class LegislativeRecord(models.Model):
    CATEGORY_ORDINANCE = 'Ordinance'
    CATEGORY_RESOLUTION = 'Resolution'
    CATEGORY_EXECUTIVE_ORDER = 'Executive Order'

    CATEGORY_CHOICES = [
        (CATEGORY_ORDINANCE, 'Ordinance'),
        (CATEGORY_RESOLUTION, 'Resolution'),
        (CATEGORY_EXECUTIVE_ORDER, 'Executive Order'),
    ]

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default=CATEGORY_ORDINANCE)
    document_number = models.CharField(max_length=100, help_text="e.g. Ord. No. 2026-04 or Res. No. 12-S2026")
    date_approved = models.DateField(help_text="Date when enacted or signed")
    pdf_file = models.FileField(upload_to='legislative/', blank=True, null=True, help_text="Upload official signed copy")
    summary = models.TextField(help_text="Concise summary or purpose of the measure")
    is_public = models.BooleanField(default=True, help_text="Display publicly on the Transparency Portal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_approved', '-created_at']
        verbose_name = 'Legislative Record'
        verbose_name_plural = 'Legislative Records & Transparency'

    def __str__(self):
        return f"{self.document_number}: {self.title} ({self.category})"

from django.contrib import admin
from apps.communications.models import Announcement, PostCategory, Post


@admin.register(PostCategory)
class PostCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'state', 'audience_type', 'purok', 'valid_from', 'valid_until', 'is_pinned', 'author', 'created_at')
    list_filter = ('category', 'state', 'audience_type', 'is_pinned')
    search_fields = ('title', 'content')

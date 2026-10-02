from django.contrib import admin
from apps.communications.models import KapitanStatus, Announcement, LegislativeRecord, PostCategory, Post


@admin.register(PostCategory)
class PostCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('author', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('content',)


@admin.register(KapitanStatus)
class KapitanStatusAdmin(admin.ModelAdmin):
    list_display = ('status', 'return_date', 'updated_by', 'updated_at')
    list_filter = ('status',)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'category_ref', 'is_pinned', 'author', 'created_at')
    list_filter = ('category', 'is_pinned')
    search_fields = ('title', 'content')


@admin.register(LegislativeRecord)
class LegislativeRecordAdmin(admin.ModelAdmin):
    list_display = ('document_number', 'title', 'category', 'date_approved', 'is_public')
    list_filter = ('category', 'is_public', 'date_approved')
    search_fields = ('document_number', 'title', 'summary')


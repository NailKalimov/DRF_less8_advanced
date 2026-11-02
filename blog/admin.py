from django.contrib import admin

from .models import Article, ArticleAttachment, Comment


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


class AttachmentInline(admin.TabularInline):
    model = ArticleAttachment
    extra = 0


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "published", "created_at")
    list_filter = ("published", "author")
    search_fields = ("title", "content")
    inlines = [CommentInline, AttachmentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("article", "author", "created_at")


@admin.register(ArticleAttachment)
class ArticleAttachmentAdmin(admin.ModelAdmin):
    list_display = ("filename", "article", "uploaded_at")

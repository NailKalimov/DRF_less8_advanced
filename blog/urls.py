"""Маршруты блога. Роутер сам создаёт URL для всех действий ViewSet.

/api/articles/                          list, create
/api/articles/<id>/                     retrieve, update, partial_update, destroy
/api/articles/<id>/publish/             @action publish
/api/articles/<id>/upload_cover/        @action upload_cover
/api/articles/<id>/add_attachment/      @action add_attachment
/api/articles/pending_review/           @action pending_review
/api/comments/                          комментарии
/api/feed/                              лента
"""

from rest_framework.routers import DefaultRouter

from .views import ArticleViewSet, CommentViewSet, FeedViewSet

router = DefaultRouter()
# basename нужен, потому что у ArticleViewSet и CommentViewSet нет
# атрибута queryset: выборку строит метод get_queryset().
router.register("articles", ArticleViewSet, basename="article")
router.register("comments", CommentViewSet, basename="comment")
router.register("feed", FeedViewSet, basename="feed")

urlpatterns = router.urls

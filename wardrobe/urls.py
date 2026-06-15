from django.urls import path
from . import views
from .views import ClothingItemViewSet, OutfitRatingViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'clothing', ClothingItemViewSet)
router.register(r'rating', OutfitRatingViewSet)

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('upload/', views.upload_clothing, name='upload_clothing'),
    path('signup/', views.signup, name="signup"),
    path('delete/<int:item_id>/', views.delete_clothing, name="delete_clothing"),
    path('generate/', views.generate_outfit, name="generate_outfit"),
    path('rate-outfit/', views.rate_outfit, name="rate_outfit"),
]

urlpatterns += router.urls

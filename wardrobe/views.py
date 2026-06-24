from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import ClothingItem, OutfitRating
from .serializers import ClothingItemSerializer, OutfitRatingSerializer
from wardrobe.ai.services.clothing_service import ClothingService
from wardrobe.ai.services.weather_service import WeatherService
from wardrobe.ai.services.outfit_generator_service import OutfitGenerationService
from wardrobe.ai.services.rating_service import RatingService
from wardrobe.ai.style_options import STYLE_OPTIONS

# Create your views here.

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, "signup.html", {"form": form})

@login_required
def home(request):
    return HttpResponse("App is working")

@login_required
def upload_clothing(request):
    if request.method == "POST":
        if request.POST.get("action") == "confirm_styles":
            item_ids = request.POST.getlist("item_ids")
            items = ClothingItem.objects.filter(
                id__in=item_ids,
                user=request.user,
            )

            try:
                for item in items:
                    selected_styles = request.POST.getlist(
                        f"styles_{item.id}"
                    )
                    ClothingService.apply_user_style_choices(
                        item,
                        selected_styles,
                    )

                messages.success(
                    request,
                    "Saved your style choices for the uploaded item(s).",
                )

            except ValueError as e:
                messages.error(request, str(e))
                return redirect("upload_clothing")

            return redirect("dashboard")

        category = request.POST.get("category")
        subcategory = request.POST.get("subcategory")
        images = request.FILES.getlist("images")
        uploaded_items = []

        for image in images:

            item = ClothingItem.objects.create(
                user=request.user,
                category=category,
                subcategory=subcategory,
                image=image,
            )

            try:
                ClothingService.process_item(item)

            except Exception as e:
                messages.warning(
                    request,
                    f"AI processing failed for {image.name}"

                )

            suggested_style = ClothingService.get_suggested_style(item)
            selected_styles = []

            if suggested_style:
                selected_styles.append(suggested_style["slug"])
            else:
                selected_styles.append("casual")

            uploaded_items.append(
                {
                    "item": item,
                    "suggested_style": suggested_style,
                    "selected_styles": selected_styles,
                    "ranked_styles": ClothingService.get_ranked_styles(
                        item,
                        limit=3,
                    ),
                }
            )

        if uploaded_items:
            return render(
                request,
                "upload.html",
                {
                    "style_options": STYLE_OPTIONS,
                    "style_confirmation_items": uploaded_items,
                },
            )

        return redirect("dashboard")

    return render(
        request,
        "upload.html",
        {
            "style_options": STYLE_OPTIONS,
        },
    )

@login_required
def dashboard(request):
    tops, bottoms, shoes = ClothingService.get_dashboard_items(
        request.user
    )

    return render(request, 'dashboard.html', {
        'tops': tops,
        'bottoms': bottoms,
        'shoes': shoes,
        'style_options': STYLE_OPTIONS,
    })

@login_required
def delete_clothing(request, item_id):

    item = get_object_or_404(
        ClothingItem,
        id=item_id,
        user=request.user,
    )

    if request.method == "POST":
        ClothingService.delete_item(item)
        return redirect("dashboard")

    return render(
        request,
        "delete_confirm.html",
        {"item": item}
    )

@login_required
@require_POST
def rate_outfit(request):

    try:
        RatingService.save_rating(
            user=request.user,
            top_id=request.POST.get("top_id"),
            bottom_id=request.POST.get("bottom_id"),
            shoe_id=request.POST.get("shoe_id"),
            style=request.POST.get("style"),
            generated_score=request.POST.get("generated_score"),
            user_rating=request.POST.get("user_rating"),
        )

        messages.success(request, "Outfit rated successfully!")

    except Exception as e:
        messages.error(request, str(e))

    return redirect(
        request.META.get("HTTP_REFERER", "dashboard")
    )

@login_required
def generate_outfit(request):

    import time
    start = time.time()

    style = request.GET.get("style", "casual")
    style_label = OutfitGenerationService.get_style_label(style)
    try:
        limit = int(request.GET.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, limit)

    weather = None
    weather_profile = None

    lat = request.GET.get("lat")
    lon = request.GET.get("lon")

    if lat and lon:
        try:
            weather = WeatherService.get_weather(lat, lon)
            weather_profile = WeatherService.get_weather_profile(weather)
        except Exception as e:
            messages.warning(
                request,
                f"Weather unavailable: {e}",
            )

    try:
        outfits, has_more = OutfitGenerationService.generate_outfits(
            user=request.user,
            style=style,
            weather_profile=weather_profile,
            limit=limit,
        )
        error = None
    except ValueError as e:
        outfits = []
        has_more = False
        error = str(e)
    
    print(
        f"TOTAL generate_outfit: {time.time() - start:.2f}s"
    )
        
    return render(
        request,
        "generate.html",
        {
            "outfits": outfits,
            "style": style,
            "style_label": style_label,
            "style_options": STYLE_OPTIONS,
            "weather": weather,
            "has_more": has_more,
            "next_limit": limit + 10,
            "error": error,
            "lat": lat,
            "lon": lon,
        }
    )

class ClothingItemViewSet(viewsets.ModelViewSet):
    queryset = ClothingItem.objects.all()
    serializer_class = ClothingItemSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend]

    filterset_fields = [
        'category',
        'subcategory',
        'material',
        'breathability',
        'weight',
    ]

    search_fields = [
        'material',
        'subcategory',
    ]

    def get_queryset(self):
        return ClothingItem.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class OutfitRatingViewSet(viewsets.ModelViewSet):
    queryset = OutfitRating.objects.all()
    serializer_class = OutfitRatingSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend]

    filterset_fields = [
        'style',
        'generated_score',
        'user_rating',
    ]

    def get_queryset(self):
        return OutfitRating.objects.filter(
            top_item__user = self.request.user
        )
    
    def perform_create(self, serializer):
        serializer.save()

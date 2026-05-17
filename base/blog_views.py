from django.shortcuts import render
from django.http import Http404
from base.blog_data import ARTICLES, get_article


def blog_index(request):
    return render(request, 'home/blog_index.html', {
        'articles': ARTICLES,
    })


def blog_detail(request, slug):
    article = get_article(slug)
    if not article:
        raise Http404
    articles_recents = [a for a in ARTICLES if a['slug'] != slug][:3]
    return render(request, 'home/blog_article.html', {
        'article': article,
        'articles_recents': articles_recents,
    })

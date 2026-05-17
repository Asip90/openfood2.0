from django.shortcuts import render

PAYS_DATA = {
    'benin': {
        'nom': 'Bénin',
        'ville_principale': 'Cotonou',
        'autres_villes': ['Porto-Novo', 'Parakou', 'Abomey-Calavi'],
        'monnaie': 'FCFA',
        'operateurs_paiement': ['MTN MoMo', 'Moov Money'],
        'slug': 'benin',
        'title': 'Menu Digital QR Code pour Restaurants au Bénin — OpenFood',
        'meta_description': 'Créez votre menu digital QR Code en 5 minutes pour votre restaurant à Cotonou ou ailleurs au Bénin. Gratuit pour démarrer. Commandes en temps réel. Paiement MTN MoMo.',
        'h1': 'Le menu digital QR Code pour les restaurants du Bénin',
        'intro': 'OpenFood permet aux restaurateurs de Cotonou, Porto-Novo et de tout le Bénin de digitaliser leur carte en 5 minutes. Vos clients scannent, commandent et vous payez en FCFA via MTN MoMo ou Moov Money.',
        'stat_restaurants': '+300',
        'schema_area': 'Bénin',
    },
    'cote-divoire': {
        'nom': "Côte d'Ivoire",
        'ville_principale': 'Abidjan',
        'autres_villes': ['Bouaké', 'Daloa', 'Yamoussoukro'],
        'monnaie': 'FCFA',
        'operateurs_paiement': ['Orange Money', 'MTN MoMo', 'Wave', 'Moov Money'],
        'slug': 'cote-divoire',
        'title': "Menu Digital QR Code pour Restaurants en Côte d'Ivoire — OpenFood",
        'meta_description': "Digitalisez votre maquis ou restaurant à Abidjan et partout en Côte d'Ivoire. Menu QR Code, commandes en ligne, paiement Orange Money, Wave et MTN MoMo. Gratuit pour démarrer.",
        'h1': "Le menu digital QR Code pour les restaurants et maquis de Côte d'Ivoire",
        'intro': "OpenFood est la solution SaaS choisie par des centaines de restaurateurs en Côte d'Ivoire pour digitaliser leur menu, gérer les commandes en temps réel et accepter les paiements Orange Money, Wave et MTN MoMo.",
        'stat_restaurants': '+300',
        'schema_area': "Côte d'Ivoire",
    },
    'senegal': {
        'nom': 'Sénégal',
        'ville_principale': 'Dakar',
        'autres_villes': ['Thiès', 'Saint-Louis', 'Ziguinchor'],
        'monnaie': 'FCFA',
        'operateurs_paiement': ['Wave', 'Orange Money', 'Free Money'],
        'slug': 'senegal',
        'title': 'Menu Digital QR Code pour Restaurants au Sénégal — OpenFood',
        'meta_description': 'Créez votre menu digital QR Code pour votre restaurant à Dakar ou au Sénégal. Paiement Wave et Orange Money. Commandes en temps réel. Gratuit pour démarrer.',
        'h1': 'Le menu digital QR Code pour les restaurants du Sénégal',
        'intro': "OpenFood accompagne les restaurateurs de Dakar et de tout le Sénégal dans la digitalisation de leur carte. Vos clients scannent, commandent et paient via Wave ou Orange Money — sans application à installer.",
        'stat_restaurants': '+300',
        'schema_area': 'Sénégal',
    },
    'mali': {
        'nom': 'Mali',
        'ville_principale': 'Bamako',
        'autres_villes': ['Sikasso', 'Mopti', 'Gao'],
        'monnaie': 'FCFA',
        'operateurs_paiement': ['Orange Money', 'Moov Money'],
        'slug': 'mali',
        'title': 'Menu Digital QR Code pour Restaurants au Mali — OpenFood',
        'meta_description': 'Digitalisez votre restaurant à Bamako et au Mali avec OpenFood. Menu QR Code, commandes en ligne, paiement mobile money. Gratuit pour démarrer.',
        'h1': 'Le menu digital QR Code pour les restaurants du Mali',
        'intro': "OpenFood permet aux restaurateurs de Bamako et de tout le Mali de proposer un menu digital moderne via QR Code. Vos clients commandent depuis leur téléphone sans aucune application à installer.",
        'stat_restaurants': '+300',
        'schema_area': 'Mali',
    },
}


def landing_pays(request, pays_slug):
    data = PAYS_DATA.get(pays_slug)
    if not data:
        from django.http import Http404
        raise Http404
    return render(request, 'home/landing_pays.html', {'pays': data})

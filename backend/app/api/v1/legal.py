from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/legal")


def _legal_page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title} | RPG Agent Company</title>
    <style>
      :root {{
        color-scheme: light;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #161616;
        background: #f7f7f2;
      }}
      body {{
        margin: 0;
        padding: 48px 20px;
      }}
      main {{
        max-width: 820px;
        margin: 0 auto;
        background: #fff;
        border: 1px solid #deded6;
        padding: 36px;
      }}
      h1 {{
        margin: 0 0 8px;
        font-size: 34px;
        line-height: 1.1;
      }}
      h2 {{
        margin: 28px 0 8px;
        font-size: 19px;
      }}
      p, li {{
        color: #333;
        font-size: 16px;
        line-height: 1.65;
      }}
      ul {{
        padding-left: 22px;
      }}
      .muted {{
        color: #666;
      }}
      a {{
        color: #111;
      }}
      @media (max-width: 640px) {{
        body {{
          padding: 18px 12px;
        }}
        main {{
          padding: 24px;
        }}
      }}
    </style>
  </head>
  <body>
    <main>{body}</main>
  </body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy() -> HTMLResponse:
    return _legal_page(
        "Politique de confidentialité",
        """
      <h1>Politique de confidentialité</h1>
      <p class="muted">Dernière mise à jour : 12 juin 2026</p>

      <p>
        RPG Agent Company est une application exploitée par The Social Company of Paris.
        Cette politique explique quelles données nous traitons lorsque vous utilisez
        l'application, les sites générés, les paiements Stripe et les fonctionnalités publicitaires.
      </p>

      <h2>Données collectées</h2>
      <ul>
        <li>Informations de compte et d'identification nécessaires à l'utilisation de l'application.</li>
        <li>Informations business fournies dans l'application : nom, description, produits, prix, contenus et préférences.</li>
        <li>Données techniques : journaux serveur, événements d'utilisation, erreurs, adresse IP et informations de navigateur.</li>
        <li>Données liées aux paiements et revenus traitées via Stripe.</li>
        <li>Données publicitaires et d'analyse, notamment événements Meta Pixel, conversions, campagnes, impressions, clics et dépenses.</li>
      </ul>

      <h2>Utilisation des données</h2>
      <p>
        Nous utilisons ces données pour fournir l'application, générer et héberger des sites,
        configurer les paiements, créer et suivre des campagnes publicitaires, améliorer la qualité
        du service, prévenir les abus et répondre aux demandes de support.
      </p>

      <h2>Partage avec des prestataires</h2>
      <p>
        Nous pouvons partager les données nécessaires avec des prestataires utilisés pour fournir
        le service, notamment Stripe pour les paiements, Meta pour les publicités et l'analyse,
        OpenAI ou d'autres fournisseurs d'IA pour la génération de contenus, ainsi que Render et
        Cloudflare pour l'hébergement et le stockage.
      </p>

      <h2>Conservation</h2>
      <p>
        Les données sont conservées aussi longtemps que nécessaire pour fournir le service,
        respecter nos obligations légales, résoudre les litiges et maintenir la sécurité de la plateforme.
      </p>

      <h2>Vos droits</h2>
      <p>
        Selon votre lieu de résidence, vous pouvez demander l'accès, la correction, l'export ou la
        suppression de vos données personnelles. Vous pouvez également vous opposer à certains traitements.
      </p>

      <h2>Vente de données</h2>
      <p>
        Nous ne vendons pas vos données personnelles.
      </p>

      <h2>Contact</h2>
      <p>
        Pour toute demande liée à la confidentialité ou à vos données, contactez-nous à
        <a href="mailto:Alex@thesocialcie.com">Alex@thesocialcie.com</a>.
      </p>
        """,
    )


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms() -> HTMLResponse:
    return _legal_page(
        "Conditions d'utilisation",
        """
      <h1>Conditions d'utilisation</h1>
      <p class="muted">Dernière mise à jour : 12 juin 2026</p>

      <p>
        En utilisant RPG Agent Company, vous acceptez d'utiliser l'application conformément aux lois
        applicables et aux conditions des services tiers connectés, notamment Stripe, Meta et les
        fournisseurs d'IA utilisés pour générer du contenu.
      </p>

      <h2>Utilisation du service</h2>
      <p>
        L'application aide à créer des sites, configurer des paiements, générer du contenu marketing
        et gérer des campagnes publicitaires. Vous restez responsable des informations, produits,
        prix, budgets et contenus que vous approuvez ou publiez.
      </p>

      <h2>Services tiers</h2>
      <p>
        Certaines fonctionnalités dépendent de services tiers. Leur disponibilité, leurs règles et
        leurs coûts peuvent varier selon leurs propres conditions d'utilisation.
      </p>

      <h2>Contact</h2>
      <p>
        Pour toute question, contactez-nous à
        <a href="mailto:Alex@thesocialcie.com">Alex@thesocialcie.com</a>.
      </p>
        """,
    )


@router.get("/data-deletion", response_class=HTMLResponse, include_in_schema=False)
async def data_deletion() -> HTMLResponse:
    return _legal_page(
        "Suppression des données",
        """
      <h1>Suppression des données</h1>
      <p class="muted">Dernière mise à jour : 12 juin 2026</p>

      <p>
        Vous pouvez demander la suppression des données associées à votre compte RPG Agent Company.
      </p>

      <h2>Comment faire une demande</h2>
      <p>
        Envoyez un e-mail à <a href="mailto:Alex@thesocialcie.com">Alex@thesocialcie.com</a>
        avec l'objet "Demande de suppression de données" et l'adresse e-mail associée à votre compte.
      </p>

      <h2>Délai de traitement</h2>
      <p>
        Nous traiterons votre demande dans un délai raisonnable, sous réserve des données que nous
        devons conserver pour respecter nos obligations légales, fiscales, de sécurité ou de prévention
        des abus.
      </p>
        """,
    )

import { SITE } from './site'

/** Логотип издания для Google (NewsArticle.publisher.logo): квадрат, растровый */
export const LOGO_URL = `${SITE.url}/brand/publisher-logo.png`

type Social = Record<string, string | null | undefined> | null | undefined

export function sameAs(social: Social): string[] {
  return Object.values(social || {}).filter((v): v is string => typeof v === 'string' && /^https?:\/\//.test(v))
}

export function organizationLd(social: Social) {
  return {
    '@type': 'NewsMediaOrganization',
    '@id': `${SITE.url}/#org`,
    name: SITE.name,
    url: SITE.url,
    logo: { '@type': 'ImageObject', url: LOGO_URL, width: 600, height: 600 },
    sameAs: sameAs(social),
  }
}

/** Главная: издание + сайт с поиском (Google может показать строку поиска по сайту) */
export function siteLd(social: Social) {
  return {
    '@context': 'https://schema.org',
    '@graph': [
      organizationLd(social),
      {
        '@type': 'WebSite',
        '@id': `${SITE.url}/#website`,
        url: SITE.url,
        name: SITE.name,
        alternateName: ['TechTalq', 'Техталк', 'TechTalQ — Технология қазақша'],
        inLanguage: 'kk',
        publisher: { '@id': `${SITE.url}/#org` },
        potentialAction: {
          '@type': 'SearchAction',
          target: { '@type': 'EntryPoint', urlTemplate: `${SITE.url}/izdeu?q={search_term_string}` },
          'query-input': 'required name=search_term_string',
        },
      },
    ],
  }
}

export function breadcrumbsLd(items: { name: string; url: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({ '@type': 'ListItem', position: i + 1, name: it.name, item: it.url })),
  }
}

/** JSON для <script type="application/ld+json"> без риска закрыть тег */
export function ldJson(data: unknown): string {
  return JSON.stringify(data).replace(/</g, '\\u003c')
}

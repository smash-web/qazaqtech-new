import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { RichText } from '@payloadcms/richtext-lexical/react'
import { SourcesPanel } from '@/components/Panels'
import { pageBySlug } from '@/lib/cms'

type Props = { params: Promise<{ slug: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = await pageBySlug((await params).slug)
  return p ? { title: p.title, description: p.summary || undefined, alternates: { canonical: `/aqparat/${p.slug}` } } : {}
}

export default async function InfoPage({ params }: Props) {
  const page = await pageBySlug((await params).slug)
  if (!page) notFound()
  return (
    <div className="info-page">
      <h1 className="article__title">{page.title}</h1>
      {page.summary && <p className="article__lead">{page.summary}</p>}
      <div className="prose"><RichText data={page.content as never} /></div>
      {page.slug === 'biz-turaly' && <SourcesPanel />}
    </div>
  )
}

import { EditorProvider } from '@/contexts/EditorContext'
import { EditorLayout } from '@/components/editor/EditorLayout'
import '@/components/editor/editor.css'

export default async function EditorPage({
  params,
}: {
  params: Promise<{ jobId: string }>
}) {
  const { jobId } = await params

  return (
    <EditorProvider jobId={jobId}>
      <EditorLayout />
    </EditorProvider>
  )
}

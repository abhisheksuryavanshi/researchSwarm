import { useParams } from 'react-router-dom'
import { ToolCatalog } from '../components/tools/ToolCatalog'
import { ToolDetail } from '../components/tools/ToolDetail'
import { PageHeader } from '../components/ui/PageHeader'

export default function ToolsPage() {
  const { toolId } = useParams<{ toolId: string }>()

  return (
    <div>
      <PageHeader
        title={toolId ? 'Tool detail' : 'Tool catalog'}
        subtitle="Read-only registry search and binding metadata"
      />
      {toolId ? <ToolDetail toolId={toolId} /> : <ToolCatalog />}
    </div>
  )
}

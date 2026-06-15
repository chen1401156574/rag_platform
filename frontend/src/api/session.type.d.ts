declare namespace API {
  interface Session {
    created_at: string
    session_id: string
    session_name: string
    updated_at: string
    // user_id: string
  }

  interface ChatItem {
    id: number
    role: import('@/configs').ChatRole
    type: import('@/configs').ChatType
    loading?: boolean
    error?: string
    content?: string
    think?: string

    documents?: Document[]
    reference?: Reference[]
    recommended_questions?: string[]
    clarifying_questions?: string[]
    original_question?: string
    clarifications?: string
    legacy_merged_clarification?: boolean
  }

  interface Document {
    document_id: string
    document_name: string
    content_with_weight: string
  }

  interface Reference {
    id: string | number
    document_id: string
    document_name: string
    content_with_weight: string
    positions?: number[][]
    page_num_int?: number[]
  }
}

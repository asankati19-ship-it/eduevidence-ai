export type Course = { id: number; code: string; title: string };
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type DocStatus = 'processing' | 'indexed' | 'error' | 'retired';
export type Document = {
  id: number; course_id: number; course_code: string; course_title: string;
  title: string; original_filename: string; sha256: string; size_bytes: number;
  page_count: number; text_pages: number | null; status: DocStatus;
  active_revision: number; chunk_count: number; error_code: string | null;
  error_message: string | null; created_at: string; updated_at: string;
};
export type Source = {
  chunk_id: number; document_id: number; document_title: string; original_filename: string;
  page_number: number; chunk_number: number; revision: number; content: string; score: number; rank: number;
};
export type Citation = Source & { evidence_quote: string; position: number };
export type Rating = 'helpful' | 'not_helpful';
export type QuestionStatus = 'processing' | 'answered' | 'abstained' | 'provider_error' | 'validation_error' | 'processing_error';
export type Answer = {
  id: number; status: QuestionStatus; body: string | null; reason: string | null;
  provider: string; model: string | null; prompt_version: string; api_outcome: string;
  error_code: string | null; retryable: boolean; verification_passed: boolean; input_tokens: number | null;
  output_tokens: number | null; latency_ms: number | null; provider_response_id: string | null; rating: Rating | null;
};
export type Question = {
  id: number; question_text: string; course_id: number | null; document_id: number | null;
  document_title: string | null; conversation_id: string | null; status: QuestionStatus;
  request_id: string; created_at: string; completed_at: string | null;
  answer: Answer | null; sources: Source[]; citations: Citation[];
};
export type QuestionInput = { question: string; course_id: number | null; document_id: number | null; conversation_id: string };
export type AuditEvent = {
  id: number; event_type: string; outcome: string; detail: string | null;
  request_id: string; question_id: number | null; document_id: number | null; created_at: string;
};
export type Overview = {
  documents: { total: number; indexed: number; errors: number; processing: number; chunks: number };
  questions: { total: number; answered: number; verified: number; abstained: number; provider_errors: number; validation_errors: number; processing_errors: number; processing: number };
  feedback: { total: number; helpful: number; not_helpful: number };
  activity: AuditEvent[];
  trend: { day: string; total: number; answered: number }[];
};
export type SystemStatus = {
  database: { status: string; schema_version: number };
  provider: { name: string; model: string; configured: boolean; timeout_seconds: number; max_retries: number };
  retrieval: { engine: string; top_k: number; min_score: number; min_query_terms: number; min_query_overlap: number; chunk_words: number; chunk_overlap: number };
  upload: { max_mb: number; max_pages: number };
  learner: { id: number; display_name: string };
  mode: string;
};


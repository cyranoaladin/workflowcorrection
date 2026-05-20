export type EmbeddingStatus = "idle" | "queued" | "embedded" | "failed" | null;

export type Exam = {
  id: string;
  title: string;
  level: string | null;
  session: string | null;
  subject_pdf_path: string | null;
  correction_pdf_path: string | null;
  rubric_pdf_path: string | null;
  rubric_json: Record<string, unknown> | null;
  total_points: string;
  embedding_status: EmbeddingStatus;
  embedded_chunks_count: number | null;
  embedded_at: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeDocument = {
  id: string;
  exam_id: string | null;
  kind: "correction" | "rubric" | "syllabus" | "user_doc";
  title: string | null;
  source_path: string;
  content_hash: string;
  chunks_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type KnowledgeListResponse = {
  documents: KnowledgeDocument[];
  total_chunks: number;
};

export type EmbedResponse = {
  status: "queued" | "completed" | "failed" | string;
  task_id: string | null;
  chunks_count: number | null;
};

export type StudentCopy = {
  id: string;
  exam_id: string;
  student_name: string | null;
  copy_code: string | null;
  original_pdf_path: string;
  status: string;
  processing_task_id: string | null;
  total_score: string | null;
  confidence: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type CopyPage = {
  id: string;
  copy_id: string;
  page_number: number;
  original_image_path: string;
  processed_image_path: string | null;
  width: number | null;
  height: number | null;
  created_at: string;
};

export type Transcription = {
  id: string;
  copy_id: string;
  page_id: string | null;
  question_id: string | null;
  source: string | null;
  input_image_type: string | null;
  raw_text: string | null;
  raw_latex: string | null;
  final_text: string | null;
  final_latex: string | null;
  raw_json: Record<string, unknown> | null;
  confidence: number | null;
  needs_human_review: boolean;
  error_message: string | null;
  created_at: string;
};

export type IntegrationsStatus = {
  mathpix: { configured: boolean };
  azure_document_intelligence: { configured: boolean };
  openai: { configured: boolean };
};

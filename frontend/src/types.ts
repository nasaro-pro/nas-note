export type Health = {
  status: string;
  ffmpeg: boolean;
  db: boolean;
  groq_key: boolean;
  gemini_key: boolean;
};

export type Chunk = {
  chunk_index: number;
  filename?: string;
  file_size?: number;
  status: string;
  retry_count?: number;
};

export type Analysis = {
  overall_summary: string;
  extracted_info: string[];
  glossary: string[];
  key_points: string[];
  detailed_summary: string;
  decisions: string[];
  todos: string[];
  important: string[];
};

export type SavedFile = {
  kind: "original" | "chunk" | "transcript" | "full" | "summary" | "analysis";
  name: string;
  size: number;
};

export type Project = {
  id: number;
  title: string;
  original_filename: string;
  date: string;
  rel_dir: string;
  duration: number | null;
  file_size: number | null;
  status: string;
  error_message: string | null;
  created_at: string;
  chunks: Chunk[];
  percent: number;
  analysis?: Analysis | null;
  transcript?: string;
  analysis_text?: string;
  video_url?: string | null;
  files?: SavedFile[];
};

export type Note = {
  id: string;
  title: string;
  body: string;
  date: string;
  date_label?: string;
  updated_at: string;
  created_at?: string;
};

export type SearchHit = {
  project_id: number;
  title: string;
  status: string;
  date: string;
  snippet: string;
  source: "title" | "transcript" | "analysis";
};

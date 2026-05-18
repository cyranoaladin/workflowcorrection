"use client";
import Link from "next/link";
import { BookOpen, Calendar, ChevronRight, FileStack } from "lucide-react";
import type { Exam } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

export function ExamCard({ exam }: { exam: Exam }) {
  return (
    <Link
      href={`/exams/${exam.id}`}
      className="group flex items-center gap-4 rounded-xl border border-gray-200/80 bg-white p-4 hover:shadow-md hover:border-gray-300/80 transition-all duration-200"
    >
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gray-100 text-gray-500 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
        <BookOpen className="h-5 w-5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900 truncate">{exam.title}</span>
          {exam.level && (
            <span className="badge bg-indigo-50 text-indigo-600 shrink-0">{exam.level}</span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
          {exam.session && <span className="font-medium">{exam.session}</span>}
          <span className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {formatRelative(exam.created_at)}
          </span>
          <span className="flex items-center gap-1">
            <FileStack className="h-3 w-3" />
            {exam.total_points} pts
          </span>
        </div>
      </div>
      <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-indigo-500 transition-colors" />
    </Link>
  );
}


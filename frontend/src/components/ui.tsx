import { ChevronLeft, ChevronRight, X } from "lucide-react";
import type React from "react";

export function Badge({
  children,
  tone = "neutral"
}: {
  children: React.ReactNode;
  tone?: "neutral" | "good" | "bad";
}) {
  const colors =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : tone === "bad"
        ? "border-rose-200 bg-rose-50 text-rose-700"
        : "border-line bg-panel text-slate-700";
  return <span className={`inline-flex rounded-md border px-2 py-1 text-xs ${colors}`}>{children}</span>;
}

export function Section({
  title,
  action,
  children
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-line bg-white">
      <div className="flex h-12 items-center justify-between border-b border-line px-4">
        <h3 className="text-sm font-semibold">{title}</h3>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`h-9 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-accent ${props.className || ""}`}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`h-9 w-full rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-accent ${props.className || ""}`}
    />
  );
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`min-h-24 w-full rounded-md border border-line px-3 py-2 font-mono text-sm outline-none focus:border-accent ${props.className || ""}`}
    />
  );
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "dark",
  disabled = false,
  title
}: {
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "dark" | "light";
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      type={type}
      onClick={() => onClick?.()}
      disabled={disabled}
      title={title}
      className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm ${
        variant === "dark" ? "bg-ink text-white" : "border border-line bg-white text-ink"
      } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      {children}
    </button>
  );
}

export function Modal({
  title,
  open,
  onClose,
  children
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4 py-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-full w-full max-w-2xl overflow-hidden rounded-md border border-line bg-white shadow-xl"
      >
        <div className="flex h-12 items-center justify-between border-b border-line px-4">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            title="Close"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line bg-white text-ink"
          >
            <X size={16} />
          </button>
        </div>
        <div className="max-h-[calc(100vh-8rem)] overflow-auto p-4">{children}</div>
      </div>
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  if (total <= pageSize) return null;

  const totalPages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
      <span>
        {start}-{end} of {total}
      </span>
      <div className="flex items-center gap-2">
        <Button
          onClick={() => onPageChange(Math.max(1, page - 1))}
          variant="light"
          disabled={page <= 1}
          title="Previous page"
        >
          <ChevronLeft size={15} />
          Prev
        </Button>
        <span className="min-w-16 text-center">
          {page} / {totalPages}
        </span>
        <Button
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          variant="light"
          disabled={page >= totalPages}
          title="Next page"
        >
          Next
          <ChevronRight size={15} />
        </Button>
      </div>
    </div>
  );
}

export function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-line bg-white p-4">
      <div className="text-sm text-slate-600">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

export function DataTable({ columns, rows }: { columns: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="overflow-auto">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead className="bg-panel text-slate-600">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-3 py-2 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr className="border-t border-line">
              <td className="px-3 py-5 text-slate-500" colSpan={columns.length}>
                No data
              </td>
            </tr>
          )}
          {rows.map((row, index) => (
            <tr key={index} className="border-t border-line">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="max-w-[360px] whitespace-normal break-words px-3 py-2 align-middle">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

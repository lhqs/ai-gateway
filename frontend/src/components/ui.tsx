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
      className="h-9 w-full rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-accent"
    />
  );
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className="min-h-24 w-full rounded-md border border-line px-3 py-2 font-mono text-sm outline-none focus:border-accent"
    />
  );
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "dark"
}: {
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "dark" | "light";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm ${
        variant === "dark" ? "bg-ink text-white" : "border border-line bg-white text-ink"
      }`}
    >
      {children}
    </button>
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
                <td key={cellIndex} className="max-w-[320px] truncate px-3 py-2 align-top">
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

/**
 * Extract a human-readable error message from an axios error or any error object.
 *
 * The backend uses a custom exception handler that returns:
 *   { "error": "HTTPException", "message": "..." }
 *
 * Standard FastAPI/Starlette errors use:
 *   { "detail": "..." }
 *
 * This helper checks all known fields before falling back to err.message.
 */
export function extractErrorMessage(err: unknown, fallback = '操作失败'): string {
  if (!err) return fallback;
  const e = err as any;
  return (
    e?.response?.data?.detail ||
    e?.response?.data?.message ||
    e?.message ||
    fallback
  );
}

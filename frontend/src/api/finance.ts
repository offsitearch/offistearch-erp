import { UPLOAD_TIMEOUT_MS, api } from './client';
import type {
  Expense,
  FinanceOverview,
  Invoice,
  InvoiceCreateInput,
  PaymentMethod,
  PayrollMonth,
  PayrollRun,
} from '../lib/types';

export interface InvoiceListParams {
  status?: string;
  client_id?: number;
  search?: string;
}

/** Fetches a filtered list of invoices. */
export async function getInvoices(params: InvoiceListParams = {}): Promise<Invoice[]> {
  const { data } = await api.get<{ items: Invoice[] }>('/invoices', { params });
  return data.items ?? [];
}

/** Fetches a single invoice by ID. */
export async function getInvoice(id: number): Promise<Invoice> {
  const { data } = await api.get<Invoice>(`/invoices/${id}`);
  return data;
}

/** Creates a new invoice. */
export async function createInvoice(payload: InvoiceCreateInput): Promise<Invoice> {
  const { data } = await api.post<Invoice>('/invoices', payload);
  return data;
}

/** Updates an existing invoice. */
export async function updateInvoice(id: number, payload: Partial<InvoiceCreateInput>): Promise<Invoice> {
  const { data } = await api.patch<Invoice>(`/invoices/${id}`, payload);
  return data;
}

/** Sends an invoice to the client. */
export async function sendInvoice(id: number): Promise<Invoice> {
  const { data } = await api.post<Invoice>(`/invoices/${id}/send`);
  return data;
}

/** Records a payment against an invoice. */
export async function recordInvoicePayment(
  id: number,
  payload: { amount: number; payment_date: string; method: PaymentMethod },
): Promise<Invoice> {
  const { data } = await api.post<Invoice>(`/invoices/${id}/payment`, payload);
  return data;
}

/** Downloads an invoice as a PDF file. */
export async function downloadInvoicePdf(id: number): Promise<void> {
  const response = await api.get(`/invoices/${id}/pdf`, { responseType: 'blob' });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = `invoice-${id}.pdf`;
  link.click();
  URL.revokeObjectURL(url);
}

export interface ExpenseCreateInput {
  category: string;
  amount: number;
  description?: string;
  expense_date?: string;
  project_id?: number | null;
  paid_by?: string;
  currency?: string;
  exchange_rate?: number;
}

/** Fetches a filtered list of expenses. */
export async function getExpenses(params: { status?: string; category?: string } = {}): Promise<Expense[]> {
  const { data } = await api.get<{ items: Expense[] }>('/expenses', { params });
  return data.items ?? [];
}

/** Creates a new expense record. */
export async function createExpense(payload: ExpenseCreateInput): Promise<Expense> {
  const { data } = await api.post<Expense>('/expenses', payload);
  return data;
}

/** Approves or rejects an expense record. */
export async function approveExpense(id: number, approve: boolean): Promise<Expense> {
  const { data } = await api.patch<Expense>(`/expenses/${id}/approve`, { approve });
  return data;
}

/** Uploads a receipt file for an expense. */
export async function uploadExpenseReceipt(id: number, file: File): Promise<Expense> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<Expense>(`/expenses/${id}/receipt`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: UPLOAD_TIMEOUT_MS,
  });
  return data;
}

/** Downloads the receipt for an expense as a blob. */
export async function downloadExpenseReceipt(id: number): Promise<void> {
  const response = await api.get(`/expenses/${id}/receipt`, { responseType: 'blob' });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.click();
  URL.revokeObjectURL(url);
}

/** Fetches the month payroll workbench: runs + build preview. */
export async function getPayroll(month: number, year: number): Promise<PayrollMonth> {
  const { data } = await api.get<PayrollMonth>('/payroll', { params: { month, year } });
  return data;
}

/** Fetches a single payroll run by id. */
export async function getPayrollRun(runId: number): Promise<PayrollRun> {
  const { data } = await api.get<PayrollRun>(`/payroll/runs/${runId}`);
  return data;
}

/** Creates a new (draft) payroll run for a month. */
export async function createPayrollRun(month: number, year: number, title: string): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>('/payroll/runs', { month, year, title });
  return data;
}

/** Adds employees to a draft run. */
export async function addPayrollEntries(runId: number, userIds: number[]): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>(`/payroll/runs/${runId}/entries`, { user_ids: userIds });
  return data;
}

/** Removes an employee from a draft run. */
export async function removePayrollEntry(runId: number, userId: number): Promise<PayrollRun> {
  const { data } = await api.delete<PayrollRun>(`/payroll/runs/${runId}/entries/${userId}`);
  return data;
}

/** Updates working days / prorate / notes on a draft entry. */
export async function updatePayrollEntry(
  runId: number,
  userId: number,
  payload: { working_days?: number; prorate?: boolean; notes?: string },
): Promise<PayrollRun> {
  const { data } = await api.put<PayrollRun>(`/payroll/runs/${runId}/entries/${userId}`, payload);
  return data;
}

/** Adds an audited bonus / deduction line to a draft entry. */
export async function addPayrollAdjustment(
  runId: number,
  userId: number,
  payload: { kind: 'addition' | 'deduction'; category: string; label: string; amount: number },
): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>(
    `/payroll/runs/${runId}/entries/${userId}/adjustments`,
    payload,
  );
  return data;
}

/** Removes an audited adjustment line from a draft entry. */
export async function removePayrollAdjustment(runId: number, adjustmentId: number): Promise<PayrollRun> {
  const { data } = await api.delete<PayrollRun>(
    `/payroll/runs/${runId}/adjustments/${adjustmentId}`,
  );
  return data;
}

/** Moves a draft run into the review stage. */
export async function submitPayrollReview(runId: number): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>(`/payroll/runs/${runId}/submit-review`);
  return data;
}

/** Approves a single entry in a review-stage run. */
export async function approvePayrollEntry(runId: number, userId: number): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>(`/payroll/runs/${runId}/entries/${userId}/approve`);
  return data;
}

/** Reopens a review/processed run back to draft. */
export async function reopenPayrollRun(runId: number): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>(`/payroll/runs/${runId}/reopen`);
  return data;
}

/** Finalises a fully-approved run and freezes payslips. */
export async function processPayrollRun(runId: number): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>(`/payroll/runs/${runId}/process`);
  return data;
}

/** Marks a processed run as paid. */
export async function markPayrollRunPaid(
  runId: number,
  payload: { payment_method?: string; payment_reference?: string },
): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>(`/payroll/runs/${runId}/mark-paid`, payload);
  return data;
}

/** Cancels a draft/review run. */
export async function cancelPayrollRun(runId: number): Promise<PayrollRun> {
  const { data } = await api.post<PayrollRun>(`/payroll/runs/${runId}/cancel`);
  return data;
}

/** Permanently deletes a draft run. */
export async function deletePayrollRun(runId: number): Promise<void> {
  await api.delete(`/payroll/runs/${runId}`);
}

/** Downloads an employee's payslip PDF from a processed run. */
export async function downloadPayslip(runId: number, userId: number): Promise<void> {
  const response = await api.get(`/payroll/runs/${runId}/payslips/${userId}`, {
    responseType: 'blob',
  });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.click();
  URL.revokeObjectURL(url);
}

/** Fetches the finance overview dashboard data for a period. */
export async function getFinanceOverview(period: string, compare = false): Promise<FinanceOverview> {
  const { data } = await api.get<FinanceOverview>('/finance/overview', {
    params: { period, compare },
  });
  return data;
}



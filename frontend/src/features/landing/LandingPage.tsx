import { Link, Navigate } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  CalendarCheck,
  Clock3,
  FolderKanban,
  Lock,
  Users,
  Wallet,
} from 'lucide-react';
import { BrandLogo, StudioMark } from '../../components/BrandLogo';
import { useAuthStore } from '../../store/authStore';

const FEATURES = [
  {
    icon: FolderKanban,
    title: 'Projects & Tasks',
    body: 'Plan site work, assign teams, and track every task from concept to handover.',
  },
  {
    icon: Users,
    title: 'Team & Attendance',
    body: 'Manage staff, org structure, leave, and daily attendance in one place.',
  },
  {
    icon: Wallet,
    title: 'Finance & Payroll',
    body: 'Invoices, expenses, and payroll controlled by an executive approval workflow.',
  },
  {
    icon: Clock3,
    title: 'Timesheets',
    body: 'Simple weekly timesheets with role-aware approvals for every project.',
  },
  {
    icon: BarChart3,
    title: 'Reports',
    body: 'Project and financial reporting with role-based visibility built in.',
  },
  {
    icon: CalendarCheck,
    title: 'Meetings & Notices',
    body: 'Schedule meetings, publish notice-board items, and keep everyone informed.',
  },
];

export default function LandingPage() {
  const accessToken = useAuthStore((s) => s.accessToken);
  if (accessToken) {
    return <Navigate to="/dashboard" replace />;
  }
  return (
    <div className="min-h-screen bg-mist text-royal">
      {/* ── Navigation ─────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 border-b border-lavender/70 bg-mist/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <BrandLogo accent="#C9964A" />
          <nav className="flex items-center gap-1 sm:gap-2">
            <a href="#features" className="hidden rounded-md px-3 py-2 text-sm font-medium text-graphite transition hover:text-royal sm:inline-block">
              Features
            </a>
            <a href="#about" className="hidden rounded-md px-3 py-2 text-sm font-medium text-graphite transition hover:text-royal sm:inline-block">
              About
            </a>
            <Link
              to="/login"
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-royal px-4 text-sm font-medium text-white transition hover:bg-navyDark"
            >
              Sign in
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </nav>
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-royal text-white">
        <div className="arch-grid-light pointer-events-none absolute inset-0" aria-hidden="true" />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-periwinkle/15 blur-3xl"
        />
        <StudioMark
          accent="#C9964A"
          className="pointer-events-none absolute -bottom-16 -right-8 h-72 w-72 text-white/[0.04]"
          aria-hidden="true"
        />

        <div className="relative z-10 mx-auto grid max-w-6xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:py-28">
          <div>
            <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-semibold tracking-wide text-white/80">
              <span className="h-1.5 w-1.5 rounded-full bg-azure" aria-hidden="true" />
              OffSiteArch ERP — Architecture Studio Management
            </span>
            <h1 className="text-display font-semibold leading-tight tracking-tight">
              Run your architecture studio on one platform.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-white/70">
              OffSiteArch ERP brings projects, teams, attendance, leave, timesheets, finance,
              and payroll together for architecture &amp; interior design firms — with role-based
              control that keeps financial data where it belongs.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to="/login"
                className="inline-flex h-11 items-center gap-2 rounded-md bg-azure px-5 text-sm font-semibold text-white transition hover:bg-white hover:text-royal"
              >
                Sign in to your workspace
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="#features"
                className="inline-flex h-11 items-center gap-2 rounded-md border border-white/20 px-5 text-sm font-medium text-white/85 transition hover:border-white/40 hover:text-white"
              >
                Explore features
              </a>
            </div>
            <p className="mt-8 flex items-center gap-2 text-xs text-white/50">
              <Lock className="h-3.5 w-3.5" aria-hidden="true" />
              Role-based access · Executive financial controls · Built for studio teams
            </p>
          </div>

          <div className="relative hidden lg:block">
            <div className="rounded-xl border border-white/10 bg-white/5 p-6 backdrop-blur">
              <div className="mb-5 flex items-center gap-3">
                <StudioMark accent="#C9964A" className="h-8 w-8" aria-hidden="true" />
                <div>
                  <div className="text-sm font-semibold text-white">Studio Overview</div>
                  <div className="text-xs text-white/50">Dashboard · live</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Projects', value: '24' },
                  { label: 'Team', value: '38' },
                  { label: 'This Month', value: '₹1.2L' },
                ].map((s) => (
                  <div key={s.label} className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <div className="text-xl font-semibold text-white">{s.value}</div>
                    <div className="mt-1 text-[11px] text-white/50">{s.label}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 space-y-2.5">
                {['Project planning', 'Site visit scheduled', 'Payroll approved'].map((item) => (
                  <div key={item} className="flex items-center gap-2.5 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/75">
                    <span className="h-1.5 w-1.5 rounded-full bg-azure" aria-hidden="true" />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ───────────────────────────────────────────────── */}
      <section id="features" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <span className="text-xs font-bold uppercase tracking-[0.18em] text-azure">Capabilities</span>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-royal sm:text-4xl">
            Everything a growing studio needs
          </h2>
          <p className="mt-4 text-sm leading-6 text-graphite">
            OffSiteArch ERP consolidates the day-to-day of an architecture and interiors practice
            into one secure, role-aware workspace.
          </p>
        </div>

        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-lavender bg-surface p-6 shadow-card transition hover:-translate-y-0.5 hover:border-azure/40"
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-haze text-azure">
                <f.icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-base font-semibold text-royal">{f.title}</h3>
              <p className="mt-2 text-sm leading-6 text-graphite">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── About ──────────────────────────────────────────────────── */}
      <section id="about" className="bg-haze">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="grid items-center gap-10 lg:grid-cols-2">
            <div>
              <span className="text-xs font-bold uppercase tracking-[0.18em] text-azure">About</span>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-royal sm:text-4xl">
                Built for architecture &amp; interior design firms
              </h2>
              <p className="mt-4 text-sm leading-7 text-graphite">
                OffSiteArch ERP is the studio management platform behind OffSiteArch, an architecture
                and interior design practice. It replaces spreadsheets and scattered tools with a
                single source of truth for projects, people, time, and money — designed from the
                ground up for how design studios actually work.
              </p>
              <Link
                to="/login"
                className="mt-6 inline-flex h-11 items-center gap-2 rounded-md bg-royal px-5 text-sm font-semibold text-white transition hover:bg-navyDark"
              >
                Already a member? Sign in
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { k: 'Projects', v: 'One workspace' },
                { k: 'People', v: 'Org & leave' },
                { k: 'Time', v: 'Timesheets' },
                { k: 'Money', v: 'Finance & payroll' },
              ].map((c) => (
                <div key={c.k} className="rounded-xl border border-lavender bg-mist p-6">
                  <div className="text-2xl font-semibold tracking-tight text-royal">{c.k}</div>
                  <div className="mt-1 text-sm text-graphite">{c.v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA + footer ───────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-royal text-white">
        <div className="arch-grid-light pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="relative z-10 mx-auto max-w-6xl px-4 py-16 text-center sm:px-6">
          <h2 className="text-3xl font-semibold tracking-tight">Ready to get started?</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm text-white/70">
            Sign in to your OffSiteArch ERP workspace to manage projects, teams, and finance.
          </p>
          <div className="mt-8 flex justify-center">
            <Link
              to="/login"
              className="inline-flex h-11 items-center gap-2 rounded-md bg-azure px-6 text-sm font-semibold text-white transition hover:bg-white hover:text-royal"
            >
              Sign in
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-lavender bg-mist">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6">
          <BrandLogo accent="#C9964A" showSubtitle={false} />
          <p className="text-xs text-graphite">
            © {new Date().getFullYear()} OffSiteArch. Architecture &amp; Interiors Studio Management.
          </p>
        </div>
      </footer>
    </div>
  );
}

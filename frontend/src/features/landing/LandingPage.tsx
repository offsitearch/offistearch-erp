import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { StudioMark } from '../../components/BrandLogo';
import { useAuthStore } from '../../store/authStore';
import { Navigate } from 'react-router-dom';

export default function LandingPage() {
  const accessToken = useAuthStore((s) => s.accessToken);
  if (accessToken) {
    return <Navigate to="/dashboard" replace />;
  }
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-mist px-4 text-royal">
      <h1 className="sr-only">OffSiteArch ERP - Architecture Studio Management Platform</h1>

      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-xl bg-royal text-white shadow-card">
        <StudioMark accent="#C9964A" className="h-9 w-9" aria-hidden="true" />
      </div>

      <p className="text-lg font-semibold tracking-tight">OffSiteArch ERP</p>
      <p className="mt-1 text-sm text-graphite">Architecture studio workspace</p>

      <Link
        to="/login"
        className="mt-8 inline-flex h-11 items-center gap-2 rounded-md bg-royal px-6 text-sm font-semibold text-white transition hover:bg-navyDark"
      >
        Sign in
        <ArrowRight className="h-4 w-4" />
      </Link>

      <p className="sr-only">
        OffSiteArch ERP is the studio management platform for architecture and interior design firms.
        Projects, team, attendance, leave, timesheets, finance and payroll in one role-aware workspace.
      </p>
    </div>
  );
}
import { NavLink, Outlet } from "react-router-dom";
import { Settings as SettingsIcon, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

const navItemBase =
  "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors";

export default function Layout() {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-4 py-3">
        <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
          <Calendar className="h-4 w-4" />
          Agent-Calendar
        </h1>
        <nav className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              cn(
                navItemBase,
                isActive
                  ? "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-white"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800",
              )
            }
          >
            今日
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                navItemBase,
                isActive
                  ? "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-white"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800",
              )
            }
          >
            <SettingsIcon className="h-3.5 w-3.5" />
            设置
          </NavLink>
        </nav>
      </header>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}

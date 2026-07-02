"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import CompanyDrawer from "@/components/CompanyDrawer";

interface DrawerContextValue {
  openDrawer: (companyId: number) => void;
}

const DrawerContext = createContext<DrawerContextValue | null>(null);

export function useDrawer(): DrawerContextValue {
  const ctx = useContext(DrawerContext);
  if (!ctx) {
    throw new Error("useDrawer must be used within a DrawerProvider");
  }
  return ctx;
}

export default function DrawerProvider({ children }: { children: ReactNode }) {
  const [openCompanyId, setOpenCompanyId] = useState<number | null>(null);

  function openDrawer(companyId: number) {
    setOpenCompanyId(companyId);
  }

  function closeDrawer() {
    setOpenCompanyId(null);
  }

  return (
    <DrawerContext.Provider value={{ openDrawer }}>
      {children}
      <CompanyDrawer
        companyId={openCompanyId}
        onClose={closeDrawer}
        onOpen={(id) => setOpenCompanyId(id)}
      />
    </DrawerContext.Provider>
  );
}

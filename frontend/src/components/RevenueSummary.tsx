import React, { useEffect, useState } from "react";
import { SecureAPI } from "../lib/secureApi";

interface RevenueData {
  property_id: string;
  total_revenue: string;
  currency: string;
  reservations_count: number;
  timezone: string;
}

interface RevenueSummaryProps {
  propertyId: string;
  month?: number;
  year?: number;
  showRaw?: boolean;
}

export const RevenueSummary: React.FC<RevenueSummaryProps> = ({
  propertyId,
  month,
  year,
  showRaw,
}) => {
  const [data, setData] = useState<RevenueData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    SecureAPI.getDashboardSummary(propertyId, { month, year }).then(
      (response) => {
        if (active) setData(response);
      },
      () => {
        if (active) setError("Revenue could not be loaded. Please try again.");
      },
    );
    return () => {
      active = false;
    };
  }, [propertyId, month, year]);

  if (error)
    return (
      <div role="alert" className="p-4 text-red-600 bg-red-50 rounded-lg">
        {error}
      </div>
    );
  if (!data)
    return (
      <div role="status" className="p-6">
        Loading revenue…
      </div>
    );

  // The API owns monetary rounding. Keep its decimal string intact in JavaScript.
  const [whole, fraction] = data.total_revenue.split(".");
  const displayTotal = `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction}`;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {showRaw && (
        <pre className="p-3 bg-gray-50 text-xs">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
      <div className="p-6">
        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
          Total Revenue
        </h2>
        <p
          className="text-3xl font-bold text-gray-900 mt-1 mb-6"
          data-testid="revenue-total"
        >
          {data.currency} {displayTotal}
        </p>
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
          <div>
            <p className="text-xs text-gray-500">Property ID</p>
            <p className="font-mono mt-1">{data.property_id}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Reservations</p>
            <p className="mt-1">{data.reservations_count} bookings</p>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-4">
          Based on check-in dates in {data.timezone}. Amounts are rounded once
          after summing.
        </p>
      </div>
    </div>
  );
};

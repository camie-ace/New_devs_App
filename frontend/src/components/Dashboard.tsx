import React, { useEffect, useState } from "react";
import { RevenueSummary } from "./RevenueSummary";
import { SecureAPI } from "../lib/secureApi";
import { useAuth } from "../contexts/AuthContext.new";

interface Property {
  id: string;
  name: string;
  timezone: string;
}

const TenantDashboard: React.FC = () => {
  const [properties, setProperties] = useState<Property[] | null>(null);
  const [selectedProperty, setSelectedProperty] = useState("");
  // The assignment's sample reservations are in March 2024.
  const [period, setPeriod] = useState("2024-03");
  const [annual, setAnnual] = useState(false);
  const [error, setError] = useState("");
  const [year, month] = period.split("-").map(Number);

  useEffect(() => {
    let active = true;
    SecureAPI.getDashboardProperties().then(
      (items: Property[]) => {
        if (!active) return;
        setProperties(items);
        setSelectedProperty(items[0]?.id || "");
      },
      () => {
        if (active)
          setError(
            "Properties could not be loaded. Please refresh to try again.",
          );
      },
    );
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="p-4 lg:p-6 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-900">
          Property Management Dashboard
        </h1>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:p-6">
          <h2 className="text-xl font-medium text-gray-900 mb-2">
            Revenue Overview
          </h2>
          <p className="text-gray-600 mb-6">
            {annual ? "Annual" : "Monthly"} performance insights for your
            properties
          </p>
          {error && (
            <p role="alert" className="text-red-600">
              {error}
            </p>
          )}
          {!properties && !error && <p role="status">Loading properties…</p>}
          {properties?.length === 0 && (
            <p>No properties are assigned to your organization.</p>
          )}
          {!!properties?.length && (
            <>
              <div className="flex flex-wrap items-end gap-4 mb-6">
                <div>
                  <label
                    htmlFor="revenue-property"
                    className="block text-sm mb-1"
                  >
                    Select Property
                  </label>
                  <select
                    id="revenue-property"
                    value={selectedProperty}
                    onChange={(e) => setSelectedProperty(e.target.value)}
                    className="border border-gray-300 rounded-md p-2"
                  >
                    {properties.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="revenue-period"
                    className="block text-sm mb-1"
                  >
                    Reporting month
                  </label>
                  <input
                    id="revenue-period"
                    type="month"
                    min="0001-01"
                    max="9998-12"
                    required
                    value={period}
                    onChange={(e) => {
                      if (e.target.value) setPeriod(e.target.value);
                    }}
                    className="border border-gray-300 rounded-md p-2"
                  />
                </div>
                <label className="flex items-center gap-2 py-2">
                  <input
                    type="checkbox"
                    checked={annual}
                    onChange={(e) => setAnnual(e.target.checked)}
                  />
                  Show full year
                </label>
              </div>
              <p className="text-sm text-gray-500 mb-3">
                Reporting period: {annual ? year : period}
              </p>
              <RevenueSummary
                key={`${selectedProperty}:${period}:${annual}`}
                propertyId={selectedProperty}
                month={annual ? undefined : month}
                year={year}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  // Remount on account changes so previous properties and revenue never remain visible.
  return user ? <TenantDashboard key={user.id} /> : null;
};

export default Dashboard;

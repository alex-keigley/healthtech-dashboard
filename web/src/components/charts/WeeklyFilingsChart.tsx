"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function WeeklyFilingsChart({
  data,
}: {
  data: { week: string; count: number }[];
}) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5e3" />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 11, fill: "#4b5f5c" }}
            tickFormatter={(value: string) => value.slice(5)}
          />
          <YAxis tick={{ fontSize: 11, fill: "#4b5f5c" }} allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" fill="#0f766e" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

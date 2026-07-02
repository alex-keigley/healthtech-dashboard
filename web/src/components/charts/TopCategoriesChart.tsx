"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function TopCategoriesChart({
  data,
}: {
  data: { category: string; count: number }[];
}) {
  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5e3" />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#4b5f5c" }} />
          <YAxis
            type="category"
            dataKey="category"
            width={180}
            tick={{ fontSize: 11, fill: "#4b5f5c" }}
          />
          <Tooltip />
          <Bar dataKey="count" fill="#14b8a6" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

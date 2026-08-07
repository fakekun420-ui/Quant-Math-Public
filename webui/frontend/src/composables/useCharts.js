import { ref, computed } from "vue";
import * as d3 from "d3";

export function useEquityChart() {
  const chartRef = ref(null);
  const data = ref([]);
  const width = ref(0);
  const height = ref(0);
  const svg = ref(null);
  const xScale = ref(null);
  const yScale = ref(null);
  const lineGenerator = ref(null);

  function initChart(container, initialData = []) {
    chartRef.value = container;
    data.value = initialData;

    if (!container) return;

    // Clear existing SVG
    d3.select(container).selectAll("*").remove();

    const rect = container.getBoundingClientRect();
    width.value = rect.width;
    height.value = rect.height;

    const margin = { top: 20, right: 20, bottom: 40, left: 60 };
    const innerWidth = width.value - margin.left - margin.right;
    const innerHeight = height.value - margin.top - margin.bottom;

    svg.value = d3
      .select(container)
      .append("svg")
      .attr("width", width.value)
      .attr("height", height.value)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    xScale.value = d3
      .scaleTime()
      .domain(d3.extent(data.value, (d) => d.timestamp))
      .range([0, innerWidth]);

    yScale.value = d3
      .scaleLinear()
      .domain([
        d3.min(data.value, (d) => d.equity),
        d3.max(data.value, (d) => d.equity),
      ])
      .range([innerHeight, 0]);

    lineGenerator.value = d3
      .line()
      .x((d) => xScale.value(d.timestamp))
      .y((d) => yScale.value(d.equity))
      .curve(d3.curveMonotoneX);

    // Grid
    svg.value
      .append("g")
      .attr("class", "grid")
      .selectAll("line")
      .data(yScale.value.ticks(5))
      .join("line")
      .attr("x1", 0)
      .attr("x2", innerWidth)
      .attr("y1", (d) => yScale.value(d))
      .attr("y2", (d) => yScale.value(d))
      .attr("stroke", "var(--border-color)")
      .attr("stroke-dasharray", "4,4");

    // X axis
    svg.value
      .append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale.value).ticks(5))
      .selectAll("text")
      .attr("fill", "var(--text-muted)")
      .attr("font-size", "0.7rem");

    // Y axis
    svg.value
      .append("g")
      .attr("class", "y-axis")
      .call(
        d3
          .axisLeft(yScale.value)
          .ticks(5)
          .tickFormat((d) => d3.format("$,.0f")(d)),
      )
      .selectAll("text")
      .attr("fill", "var(--text-muted)")
      .attr("font-size", "0.7rem");

    // Area
    svg.value
      .append("path")
      .datum(data.value)
      .attr("class", "equity-area")
      .attr("fill", "url(#equity-gradient)")
      .attr(
        "d",
        d3
          .area()
          .x((d) => xScale.value(d.timestamp))
          .y0(innerHeight)
          .y1((d) => yScale.value(d.equity))
          .curve(d3.curveMonotoneX),
      );

    // Line
    svg.value
      .append("path")
      .datum(data.value)
      .attr("class", "equity-line")
      .attr("fill", "none")
      .attr("stroke", "var(--accent-primary)")
      .attr("stroke-width", 2)
      .attr("d", lineGenerator.value);

    // Gradient
    const defs = d3.select(container).select("svg").append("defs");
    const gradient = defs
      .append("linearGradient")
      .attr("id", "equity-gradient")
      .attr("gradientUnits", "userSpaceOnUse")
      .attr("x1", 0)
      .attr("y1", innerHeight)
      .attr("x2", 0)
      .attr("y2", 0);
    gradient
      .append("stop")
      .attr("offset", "0%")
      .attr("stop-color", "var(--accent-primary)")
      .attr("stop-opacity", 0.3);
    gradient
      .append("stop")
      .attr("offset", "100%")
      .attr("stop-color", "var(--accent-primary)")
      .attr("stop-opacity", 0);
  }

  function updateChart(newData) {
    data.value = newData;
    if (!svg.value || !xScale.value || !yScale.value) return;

    const margin = { top: 20, right: 20, bottom: 40, left: 60 };
    const innerWidth = width.value - margin.left - margin.right;
    const innerHeight = height.value - margin.top - margin.bottom;

    xScale.value.domain(d3.extent(data.value, (d) => d.timestamp));
    yScale.value.domain([
      d3.min(data.value, (d) => d.equity),
      d3.max(data.value, (d) => d.equity),
    ]);

    svg.value
      .select(".x-axis")
      .transition()
      .duration(500)
      .call(d3.axisBottom(xScale.value).ticks(5));

    svg.value
      .select(".y-axis")
      .transition()
      .duration(500)
      .call(
        d3
          .axisLeft(yScale.value)
          .ticks(5)
          .tickFormat((d) => d3.format("$,.0f")(d)),
      );

    svg.value
      .select(".equity-area")
      .datum(data.value)
      .transition()
      .duration(500)
      .attr(
        "d",
        d3
          .area()
          .x((d) => xScale.value(d.timestamp))
          .y0(innerHeight)
          .y1((d) => yScale.value(d.equity))
          .curve(d3.curveMonotoneX),
      );

    svg.value
      .select(".equity-line")
      .datum(data.value)
      .transition()
      .duration(500)
      .attr("d", lineGenerator.value);
  }

  function resize() {
    if (!chartRef.value) return;

    const rect = chartRef.value.getBoundingClientRect();
    width.value = rect.width;
    height.value = rect.height;

    d3.select(chartRef.value)
      .select("svg")
      .attr("width", width.value)
      .attr("height", height.value);

    // Re-init with current data
    initChart(chartRef.value, data.value);
  }

  return {
    chartRef,
    data,
    initChart,
    updateChart,
    resize,
  };
}

export function useMiniChart() {
  const chartRef = ref(null);
  const data = ref([]);
  const color = ref("var(--accent-primary)");

  function initChart(
    container,
    initialData = [],
    chartColor = "var(--accent-primary)",
  ) {
    chartRef.value = container;
    data.value = initialData;
    color.value = chartColor;

    if (!container) return;

    d3.select(container).selectAll("*").remove();

    const rect = container.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    const svg = d3
      .select(container)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const xScale = d3
      .scaleLinear()
      .domain([0, data.value.length - 1])
      .range([0, width]);

    const yScale = d3
      .scaleLinear()
      .domain([d3.min(data.value), d3.max(data.value)])
      .range([height, 0]);

    const line = d3
      .line()
      .x((d, i) => xScale(i))
      .y((d) => yScale(d))
      .curve(d3.curveMonotoneX);

    // Area
    svg
      .append("path")
      .datum(data.value)
      .attr("fill", chartColor)
      .attr("fill-opacity", 0.2)
      .attr(
        "d",
        d3
          .area()
          .x((d, i) => xScale(i))
          .y0(height)
          .y1((d) => yScale(d))
          .curve(d3.curveMonotoneX),
      );

    // Line
    svg
      .append("path")
      .datum(data.value)
      .attr("fill", "none")
      .attr("stroke", chartColor)
      .attr("stroke-width", 1.5)
      .attr("d", line);
  }

  function updateChart(newData, chartColor) {
    data.value = newData;
    if (chartColor) color.value = chartColor;
    if (chartRef.value) {
      initChart(chartRef.value, data.value, color.value);
    }
  }

  return {
    chartRef,
    data,
    initChart,
    updateChart,
  };
}

export function useSparkline() {
  return useMiniChart();
}

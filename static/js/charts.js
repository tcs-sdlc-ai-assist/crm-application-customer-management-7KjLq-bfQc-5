(function () {
  "use strict";

  var ChartColors = {
    primary: "rgba(54, 162, 235, 1)",
    primaryLight: "rgba(54, 162, 235, 0.6)",
    success: "rgba(75, 192, 192, 1)",
    successLight: "rgba(75, 192, 192, 0.6)",
    warning: "rgba(255, 206, 86, 1)",
    warningLight: "rgba(255, 206, 86, 0.6)",
    danger: "rgba(255, 99, 132, 1)",
    dangerLight: "rgba(255, 99, 132, 0.6)",
    info: "rgba(153, 102, 255, 1)",
    infoLight: "rgba(153, 102, 255, 0.6)",
    secondary: "rgba(201, 203, 207, 1)",
    secondaryLight: "rgba(201, 203, 207, 0.6)",
    orange: "rgba(255, 159, 64, 1)",
    orangeLight: "rgba(255, 159, 64, 0.6)",
    palette: [
      "rgba(54, 162, 235, 0.7)",
      "rgba(255, 99, 132, 0.7)",
      "rgba(75, 192, 192, 0.7)",
      "rgba(255, 206, 86, 0.7)",
      "rgba(153, 102, 255, 0.7)",
      "rgba(255, 159, 64, 0.7)",
      "rgba(201, 203, 207, 0.7)",
    ],
    paletteBorder: [
      "rgba(54, 162, 235, 1)",
      "rgba(255, 99, 132, 1)",
      "rgba(75, 192, 192, 1)",
      "rgba(255, 206, 86, 1)",
      "rgba(153, 102, 255, 1)",
      "rgba(255, 159, 64, 1)",
      "rgba(201, 203, 207, 1)",
    ],
  };

  function getChartData(canvas) {
    var dataAttr = canvas.getAttribute("data-chart-data");
    if (dataAttr) {
      try {
        return JSON.parse(dataAttr);
      } catch (e) {
        console.error("Failed to parse chart data from data attribute:", e);
        return null;
      }
    }

    var scriptId = canvas.getAttribute("data-chart-json");
    if (scriptId) {
      var scriptEl = document.getElementById(scriptId);
      if (scriptEl) {
        try {
          return JSON.parse(scriptEl.textContent);
        } catch (e) {
          console.error("Failed to parse chart data from script element:", e);
          return null;
        }
      }
    }

    return null;
  }

  function getDefaultTooltipConfig() {
    return {
      mode: "index",
      intersect: false,
      backgroundColor: "rgba(0, 0, 0, 0.8)",
      titleFont: { size: 13 },
      bodyFont: { size: 12 },
      padding: 10,
      cornerRadius: 4,
    };
  }

  function getDefaultLegendConfig() {
    return {
      position: "top",
      labels: {
        usePointStyle: true,
        padding: 16,
        font: { size: 12 },
      },
    };
  }

  function formatCurrency(value) {
    if (typeof value !== "number") {
      return value;
    }
    return "$" + value.toLocaleString("en-US", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  }

  function destroyExistingChart(canvas) {
    var existingChart = Chart.getChart(canvas);
    if (existingChart) {
      existingChart.destroy();
    }
  }

  /**
   * Render a pipeline chart (bar chart) showing deal counts or values per stage.
   * Expected data format:
   * {
   *   labels: ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won"],
   *   values: [45, 32, 18, 12, 8],
   *   amounts: [150000, 280000, 320000, 180000, 450000]  // optional
   * }
   */
  function renderPipelineChart(canvasId, data) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) {
      console.error("Canvas element not found:", canvasId);
      return null;
    }

    var chartData = data || getChartData(canvas);
    if (!chartData) {
      console.error("No chart data available for pipeline chart:", canvasId);
      return null;
    }

    destroyExistingChart(canvas);

    var datasets = [
      {
        label: "Number of Deals",
        data: chartData.values || [],
        backgroundColor: ChartColors.palette.slice(0, (chartData.labels || []).length),
        borderColor: ChartColors.paletteBorder.slice(0, (chartData.labels || []).length),
        borderWidth: 1,
        borderRadius: 4,
        yAxisID: "y",
      },
    ];

    if (chartData.amounts && chartData.amounts.length > 0) {
      datasets.push({
        label: "Deal Value",
        data: chartData.amounts,
        backgroundColor: ChartColors.orangeLight,
        borderColor: ChartColors.orange,
        borderWidth: 1,
        borderRadius: 4,
        yAxisID: "y1",
      });
    }

    var scales = {
      x: {
        grid: { display: false },
        ticks: { font: { size: 12 } },
      },
      y: {
        beginAtZero: true,
        position: "left",
        title: {
          display: true,
          text: "Number of Deals",
          font: { size: 12 },
        },
        ticks: {
          precision: 0,
        },
      },
    };

    if (chartData.amounts && chartData.amounts.length > 0) {
      scales.y1 = {
        beginAtZero: true,
        position: "right",
        title: {
          display: true,
          text: "Deal Value ($)",
          font: { size: 12 },
        },
        grid: { drawOnChartArea: false },
        ticks: {
          callback: function (value) {
            return formatCurrency(value);
          },
        },
      };
    }

    var ctx = canvas.getContext("2d");
    return new Chart(ctx, {
      type: "bar",
      data: {
        labels: chartData.labels || [],
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: Object.assign({}, getDefaultTooltipConfig(), {
            callbacks: {
              label: function (context) {
                var label = context.dataset.label || "";
                var value = context.parsed.y;
                if (context.datasetIndex === 1) {
                  return label + ": " + formatCurrency(value);
                }
                return label + ": " + value;
              },
            },
          }),
          legend: getDefaultLegendConfig(),
          title: {
            display: !!chartData.title,
            text: chartData.title || "",
            font: { size: 16 },
          },
        },
        scales: scales,
      },
    });
  }

  /**
   * Render a sales performance chart (line chart) showing revenue over time.
   * Expected data format:
   * {
   *   labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
   *   datasets: [
   *     { label: "Revenue", data: [12000, 19000, 15000, 25000, 22000, 30000] },
   *     { label: "Target", data: [15000, 15000, 20000, 20000, 25000, 25000] }
   *   ]
   * }
   * OR simple format:
   * {
   *   labels: ["Jan", "Feb", ...],
   *   values: [12000, 19000, ...],
   *   target: [15000, 15000, ...]  // optional
   * }
   */
  function renderSalesPerformanceChart(canvasId, data) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) {
      console.error("Canvas element not found:", canvasId);
      return null;
    }

    var chartData = data || getChartData(canvas);
    if (!chartData) {
      console.error("No chart data available for sales performance chart:", canvasId);
      return null;
    }

    destroyExistingChart(canvas);

    var datasets;

    if (chartData.datasets && Array.isArray(chartData.datasets)) {
      var colorAssignments = [
        { bg: ChartColors.primaryLight, border: ChartColors.primary },
        { bg: ChartColors.dangerLight, border: ChartColors.danger },
        { bg: ChartColors.successLight, border: ChartColors.success },
        { bg: ChartColors.warningLight, border: ChartColors.warning },
        { bg: ChartColors.infoLight, border: ChartColors.info },
      ];

      datasets = chartData.datasets.map(function (ds, index) {
        var colors = colorAssignments[index % colorAssignments.length];
        return {
          label: ds.label || "Series " + (index + 1),
          data: ds.data || [],
          borderColor: ds.borderColor || colors.border,
          backgroundColor: ds.backgroundColor || colors.bg,
          fill: ds.fill !== undefined ? ds.fill : false,
          tension: ds.tension !== undefined ? ds.tension : 0.3,
          pointRadius: ds.pointRadius !== undefined ? ds.pointRadius : 4,
          pointHoverRadius: 6,
          borderWidth: 2,
          borderDash: ds.borderDash || [],
        };
      });
    } else {
      datasets = [
        {
          label: "Revenue",
          data: chartData.values || [],
          borderColor: ChartColors.primary,
          backgroundColor: ChartColors.primaryLight,
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointHoverRadius: 6,
          borderWidth: 2,
        },
      ];

      if (chartData.target && chartData.target.length > 0) {
        datasets.push({
          label: "Target",
          data: chartData.target,
          borderColor: ChartColors.danger,
          backgroundColor: "transparent",
          fill: false,
          tension: 0,
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          borderDash: [5, 5],
        });
      }
    }

    var ctx = canvas.getContext("2d");
    return new Chart(ctx, {
      type: "line",
      data: {
        labels: chartData.labels || [],
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          tooltip: Object.assign({}, getDefaultTooltipConfig(), {
            callbacks: {
              label: function (context) {
                var label = context.dataset.label || "";
                var value = context.parsed.y;
                return label + ": " + formatCurrency(value);
              },
            },
          }),
          legend: getDefaultLegendConfig(),
          title: {
            display: !!chartData.title,
            text: chartData.title || "",
            font: { size: 16 },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { font: { size: 12 } },
          },
          y: {
            beginAtZero: true,
            ticks: {
              callback: function (value) {
                return formatCurrency(value);
              },
            },
            title: {
              display: true,
              text: "Revenue ($)",
              font: { size: 12 },
            },
          },
        },
      },
    });
  }

  /**
   * Render a customer engagement chart (doughnut chart).
   * Expected data format:
   * {
   *   labels: ["Email", "Phone", "Meeting", "Social Media", "Other"],
   *   values: [35, 25, 20, 12, 8]
   * }
   */
  function renderCustomerEngagementChart(canvasId, data) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) {
      console.error("Canvas element not found:", canvasId);
      return null;
    }

    var chartData = data || getChartData(canvas);
    if (!chartData) {
      console.error("No chart data available for customer engagement chart:", canvasId);
      return null;
    }

    destroyExistingChart(canvas);

    var numLabels = (chartData.labels || []).length;
    var backgroundColors = [];
    var borderColors = [];
    for (var i = 0; i < numLabels; i++) {
      backgroundColors.push(ChartColors.palette[i % ChartColors.palette.length]);
      borderColors.push(ChartColors.paletteBorder[i % ChartColors.paletteBorder.length]);
    }

    var ctx = canvas.getContext("2d");
    return new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: chartData.labels || [],
        datasets: [
          {
            data: chartData.values || [],
            backgroundColor: chartData.colors || backgroundColors,
            borderColor: chartData.borderColors || borderColors,
            borderWidth: 2,
            hoverOffset: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "55%",
        plugins: {
          tooltip: Object.assign({}, getDefaultTooltipConfig(), {
            callbacks: {
              label: function (context) {
                var label = context.label || "";
                var value = context.parsed;
                var total = context.dataset.data.reduce(function (sum, val) {
                  return sum + val;
                }, 0);
                var percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                return label + ": " + value + " (" + percentage + "%)";
              },
            },
          }),
          legend: Object.assign({}, getDefaultLegendConfig(), {
            position: "right",
          }),
          title: {
            display: !!chartData.title,
            text: chartData.title || "",
            font: { size: 16 },
          },
        },
      },
    });
  }

  /**
   * Render a deal progression chart (stacked bar chart) showing deal stages over time.
   * Expected data format:
   * {
   *   labels: ["Q1", "Q2", "Q3", "Q4"],
   *   datasets: [
   *     { label: "Prospecting", data: [20, 25, 18, 22] },
   *     { label: "Qualification", data: [15, 18, 20, 16] },
   *     { label: "Proposal", data: [10, 12, 15, 18] },
   *     { label: "Negotiation", data: [5, 8, 10, 12] },
   *     { label: "Closed Won", data: [3, 5, 8, 10] }
   *   ]
   * }
   */
  function renderDealProgressionChart(canvasId, data) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) {
      console.error("Canvas element not found:", canvasId);
      return null;
    }

    var chartData = data || getChartData(canvas);
    if (!chartData) {
      console.error("No chart data available for deal progression chart:", canvasId);
      return null;
    }

    destroyExistingChart(canvas);

    var datasets;

    if (chartData.datasets && Array.isArray(chartData.datasets)) {
      datasets = chartData.datasets.map(function (ds, index) {
        return {
          label: ds.label || "Stage " + (index + 1),
          data: ds.data || [],
          backgroundColor: ds.backgroundColor || ChartColors.palette[index % ChartColors.palette.length],
          borderColor: ds.borderColor || ChartColors.paletteBorder[index % ChartColors.paletteBorder.length],
          borderWidth: 1,
          borderRadius: 2,
        };
      });
    } else {
      datasets = [];
    }

    var ctx = canvas.getContext("2d");
    return new Chart(ctx, {
      type: "bar",
      data: {
        labels: chartData.labels || [],
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          tooltip: Object.assign({}, getDefaultTooltipConfig(), {
            callbacks: {
              footer: function (tooltipItems) {
                var total = 0;
                tooltipItems.forEach(function (item) {
                  total += item.parsed.y;
                });
                return "Total: " + total;
              },
            },
          }),
          legend: getDefaultLegendConfig(),
          title: {
            display: !!chartData.title,
            text: chartData.title || "",
            font: { size: 16 },
          },
        },
        scales: {
          x: {
            stacked: true,
            grid: { display: false },
            ticks: { font: { size: 12 } },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            title: {
              display: true,
              text: "Number of Deals",
              font: { size: 12 },
            },
            ticks: {
              precision: 0,
            },
          },
        },
      },
    });
  }

  /**
   * Initialize all charts on the page by scanning for canvas elements
   * with the data-chart-type attribute.
   * Usage in templates:
   *   <canvas id="pipelineChart" data-chart-type="pipeline" data-chart-json="pipeline-data"></canvas>
   *   <script id="pipeline-data" type="application/json">{{ chart_data|safe }}</script>
   */
  function initAllCharts() {
    var chartCanvases = document.querySelectorAll("canvas[data-chart-type]");

    var renderers = {
      pipeline: renderPipelineChart,
      "sales-performance": renderSalesPerformanceChart,
      "customer-engagement": renderCustomerEngagementChart,
      "deal-progression": renderDealProgressionChart,
    };

    var charts = {};

    chartCanvases.forEach(function (canvas) {
      var chartType = canvas.getAttribute("data-chart-type");
      var renderer = renderers[chartType];

      if (renderer) {
        try {
          var chart = renderer(canvas.id);
          if (chart) {
            charts[canvas.id] = chart;
          }
        } catch (e) {
          console.error("Failed to render chart:", canvas.id, chartType, e);
        }
      } else {
        console.warn("Unknown chart type:", chartType, "on canvas:", canvas.id);
      }
    });

    return charts;
  }

  /**
   * Update an existing chart with new data without full re-render.
   */
  function updateChart(canvasId, newData) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) {
      console.error("Canvas element not found:", canvasId);
      return;
    }

    var chart = Chart.getChart(canvas);
    if (!chart) {
      console.error("No existing chart found on canvas:", canvasId);
      return;
    }

    if (newData.labels) {
      chart.data.labels = newData.labels;
    }

    if (newData.datasets && Array.isArray(newData.datasets)) {
      newData.datasets.forEach(function (ds, index) {
        if (chart.data.datasets[index]) {
          if (ds.data) {
            chart.data.datasets[index].data = ds.data;
          }
          if (ds.label) {
            chart.data.datasets[index].label = ds.label;
          }
        }
      });
    } else if (newData.values) {
      if (chart.data.datasets[0]) {
        chart.data.datasets[0].data = newData.values;
      }
    }

    chart.update();
  }

  /**
   * Destroy a chart instance and clean up.
   */
  function destroyChart(canvasId) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) {
      return;
    }
    destroyExistingChart(canvas);
  }

  window.CRMCharts = {
    renderPipelineChart: renderPipelineChart,
    renderSalesPerformanceChart: renderSalesPerformanceChart,
    renderCustomerEngagementChart: renderCustomerEngagementChart,
    renderDealProgressionChart: renderDealProgressionChart,
    initAllCharts: initAllCharts,
    updateChart: updateChart,
    destroyChart: destroyChart,
    colors: ChartColors,
    formatCurrency: formatCurrency,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      var autoInit = document.querySelectorAll("canvas[data-chart-type][data-chart-auto]");
      if (autoInit.length > 0) {
        initAllCharts();
      }
    });
  } else {
    var autoInit = document.querySelectorAll("canvas[data-chart-type][data-chart-auto]");
    if (autoInit.length > 0) {
      initAllCharts();
    }
  }
})();
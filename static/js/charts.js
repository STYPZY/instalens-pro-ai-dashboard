// InstaLens — Chart Utilities

Chart.defaults.color = '#8b9bc8';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'Space Mono', monospace";
Chart.defaults.font.size = 11;

function createRelationshipChart(followers, following) {
  var ctx = document.getElementById('relationshipChart');
  if (!ctx) return;

  // If both are 0, show placeholder so chart still renders
  var hasData = followers > 0 || following > 0;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: hasData ? ['Followers', 'Following'] : ['No Data'],
      datasets: [{
        data: hasData ? [followers, following] : [1],
        backgroundColor: hasData
          ? ['rgba(79,142,247,0.85)', 'rgba(45,212,191,0.85)']
          : ['rgba(255,255,255,0.06)'],
        borderColor: hasData
          ? ['rgba(79,142,247,1)', 'rgba(45,212,191,1)']
          : ['rgba(255,255,255,0.1)'],
        borderWidth: 2,
        hoverOffset: 6
      }]
    },
    options: {
      cutout: '68%',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            padding: 18,
            usePointStyle: true,
            pointStyleWidth: 8,
            color: '#8b9bc8',
            font: { family: "'DM Sans', sans-serif", size: 12 }
          }
        },
        tooltip: {
          enabled: hasData,
          backgroundColor: '#0f1525',
          borderColor: 'rgba(255,255,255,0.08)',
          borderWidth: 1,
          titleColor: '#f0f4ff',
          bodyColor: '#8b9bc8',
          padding: 12,
          cornerRadius: 8,
          titleFont: { family: "'Syne', sans-serif", weight: '700', size: 13 },
          bodyFont: { family: "'DM Sans', sans-serif", size: 12 },
          callbacks: {
            label: function(ctx) {
              return '  ' + ctx.label + ': ' + ctx.parsed;
            }
          }
        }
      }
    }
  });
}

function createInteractionChart(likes, comments) {
  var ctx = document.getElementById('interactionChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Likes', 'Comments'],
      datasets: [{
        label: 'Count',
        data: [likes, comments],
        backgroundColor: [
          'rgba(167,139,250,0.7)',
          'rgba(251,113,133,0.7)'
        ],
        borderColor: [
          'rgba(167,139,250,1)',
          'rgba(251,113,133,1)'
        ],
        borderWidth: 1.5,
        borderRadius: 6,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f1525',
          borderColor: 'rgba(255,255,255,0.08)',
          borderWidth: 1,
          titleColor: '#f0f4ff',
          bodyColor: '#8b9bc8',
          padding: 12,
          cornerRadius: 8,
          titleFont: { family: "'Syne', sans-serif", weight: '700', size: 13 },
          bodyFont: { family: "'DM Sans', sans-serif", size: 12 }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: '#8b9bc8',
            font: { family: "'DM Sans', sans-serif", size: 12 }
          },
          border: { display: false }
        },
        y: {
          beginAtZero: true,
          grace: '10%',
          grid: { color: 'rgba(255,255,255,0.04)', drawTicks: false },
          ticks: {
            color: '#4a5578',
            font: { family: "'Space Mono', monospace", size: 10 },
            padding: 10,
            precision: 0
          },
          border: { display: false, dash: [4, 4] }
        }
      }
    }
  });
}
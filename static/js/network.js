const container = document.getElementById("network")

// Build nodes and edges from template data if available
const nodes = new vis.DataSet([{ id: 1, label: "You", color: { background: "#4f8ef7", border: "#6fa3ff" }, font: { color: "#f0f4ff" } }])
const edges = new vis.DataSet([])

if (window.network_data) {
  const followers = window.network_data.followers || []
  const following = window.network_data.following || []

  // Add follower nodes (up to 100 for performance)
  followers.slice(0, 100).forEach(function(user, i) {
    nodes.add({ id: "f_" + i, label: user, color: { background: "#2dd4bf", border: "#2dd4bf" }, font: { color: "#f0f4ff", size: 10 } })
    edges.add({ from: "f_" + i, to: 1, color: { color: "rgba(45,212,191,0.3)" } })
  })

  // Add following nodes (up to 100 for performance)
  following.slice(0, 100).forEach(function(user, i) {
    nodes.add({ id: "g_" + i, label: user, color: { background: "#a78bfa", border: "#a78bfa" }, font: { color: "#f0f4ff", size: 10 } })
    edges.add({ from: 1, to: "g_" + i, color: { color: "rgba(167,139,250,0.3)" } })
  })
}

const data = { nodes: nodes, edges: edges }

const options = {
  physics: {
    barnesHut: {
      gravitationalConstant: -8000,
      springLength: 120
    }
  },
  interaction: {
    dragNodes: true,
    zoomView: true
  },
  nodes: {
    shape: "dot",
    size: 10,
    borderWidth: 1.5,
    font: { size: 11, face: "DM Sans" }
  },
  edges: {
    width: 1,
    smooth: { type: "continuous" }
  }
}

window._visNetwork = new vis.Network(container, data, options)
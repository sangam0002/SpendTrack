const chartData = JSON.parse(
    document.getElementById("chart-data").textContent
);


const categories = chartData.categories;

const amounts = chartData.amounts;


const ctx = document.getElementById("expenseChart");


new Chart(ctx, {

    type: "doughnut",

    data: {

        labels: categories,

        datasets: [{

            label: "Expenses",

            data: amounts

        }]

    },


    options: {

        responsive: true,

        maintainAspectRatio: true,

        plugins: {

            legend: {

                position: "bottom"

            }

        }

    }

});
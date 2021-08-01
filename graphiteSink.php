<?php
// Get the JSON contents
$json = file_get_contents('php://input');

// decode the json data
$data = json_decode($json);

echo $data;
?>
